import { createClient } from "npm:@supabase/supabase-js@2";


type JsonObject = Record<string, unknown>;

type PaymentStatus =
  | "PENDING"
  | "PAID"
  | "FAILED"
  | "CANCELLED"
  | "REFUNDED";


interface PaymentRecord {
  id: string;
  payment_reference: string;
  telegram_id: number;
  plan_code: string;
  provider_code: string;
  provider_reference: string | null;
  amount_rm: string | number;
  currency_code: string;
  status: PaymentStatus;
  subscription_id: string | null;
  customer_name: string;
  metadata: JsonObject | null;
}


interface CallbackResult {
  payment_reference: string;
  telegram_id: number;
  plan_code: string;
  payment_status: PaymentStatus;
  subscription_id: string | null;
  duplicate: boolean;
}


const CHECKSUM_FIELDS = [
  "record_type",
  "transaction_id",
  "exchange_reference_number",
  "exchange_transaction_id",
  "order_number",
  "currency",
  "amount",
  "payer_name",
  "payer_email",
  "payer_bank_name",
  "status",
  "status_description",
  "datetime",
] as const;


const TERMINAL_SUCCESS_STATUSES: PaymentStatus[] = [
  "PAID",
  "REFUNDED",
];


function jsonResponse(
  body: JsonObject,
  status = 200,
): Response {
  return new Response(
    JSON.stringify(body),
    {
      status,
      headers: {
        "Content-Type": "application/json",
      },
    },
  );
}


function getRequiredEnvironmentVariable(
  name: string,
): string {
  const value = Deno.env.get(name)?.trim();

  if (!value) {
    throw new Error(
      `Environment variable ${name} tidak tersedia.`,
    );
  }

  return value;
}


function constantTimeEquals(
  left: string,
  right: string,
): boolean {
  const normalizedLeft = left.toLowerCase();
  const normalizedRight = right.toLowerCase();

  if (
    normalizedLeft.length
    !== normalizedRight.length
  ) {
    return false;
  }

  let difference = 0;

  for (
    let index = 0;
    index < normalizedLeft.length;
    index += 1
  ) {
    difference |= (
      normalizedLeft.charCodeAt(index)
      ^ normalizedRight.charCodeAt(index)
    );
  }

  return difference === 0;
}


function normalizeCallbackValue(
  value: unknown,
): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value.trim();
  }

  return String(value).trim();
}


function normalizePayload(
  payload: JsonObject,
): JsonObject {
  const normalizedPayload: JsonObject = {};

  for (
    const [key, value]
    of Object.entries(payload)
  ) {
    if (
      typeof value === "string"
      && value.trim().startsWith("{")
    ) {
      try {
        const parsedValue = JSON.parse(
          value,
        );

        normalizedPayload[key] = parsedValue;
        continue;
      } catch {
        // Kekalkan string asal apabila ia bukan JSON sah.
      }
    }

    normalizedPayload[key] = value;
  }

  return normalizedPayload;
}


async function parseRequestPayload(
  request: Request,
): Promise<JsonObject> {
  const contentType = (
    request.headers.get("content-type")
    ?? ""
  ).toLowerCase();

  if (
    contentType.includes(
      "application/json",
    )
  ) {
    const payload = await request.json();

    if (
      !payload
      || typeof payload !== "object"
      || Array.isArray(payload)
    ) {
      throw new Error(
        "Payload JSON webhook tidak sah.",
      );
    }

    return normalizePayload(
      payload as JsonObject,
    );
  }

  if (
    contentType.includes(
      "application/x-www-form-urlencoded",
    )
    || contentType.includes(
      "multipart/form-data",
    )
  ) {
    const formData = await request.formData();
    const payload: JsonObject = {};

    for (
      const [key, value]
      of formData.entries()
    ) {
      if (typeof value === "string") {
        payload[key] = value;
      }
    }

    return normalizePayload(
      payload,
    );
  }

  const rawBody = (
    await request.text()
  ).trim();

  if (!rawBody) {
    throw new Error(
      "Payload webhook kosong.",
    );
  }

  try {
    const payload = JSON.parse(
      rawBody,
    );

    if (
      !payload
      || typeof payload !== "object"
      || Array.isArray(payload)
    ) {
      throw new Error(
        "Payload webhook tidak sah.",
      );
    }

    return normalizePayload(
      payload as JsonObject,
    );
  } catch {
    const searchParameters = (
      new URLSearchParams(rawBody)
    );

    const payload: JsonObject = {};

    for (
      const [key, value]
      of searchParameters.entries()
    ) {
      payload[key] = value;
    }

    if (
      Object.keys(payload).length === 0
    ) {
      throw new Error(
        "Format payload webhook tidak disokong.",
      );
    }

    return normalizePayload(
      payload,
    );
  }
}


async function createHmacSha256(
  secretKey: string,
  message: string,
): Promise<string> {
  const encoder = new TextEncoder();

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secretKey),
    {
      name: "HMAC",
      hash: "SHA-256",
    },
    false,
    [
      "sign",
    ],
  );

  const signature = await crypto.subtle.sign(
    "HMAC",
    cryptoKey,
    encoder.encode(message),
  );

  return Array.from(
    new Uint8Array(signature),
  )
    .map(
      (byte) => (
        byte
          .toString(16)
          .padStart(2, "0")
      ),
    )
    .join("");
}


async function verifyCallbackChecksum(
  payload: JsonObject,
  apiSecretKey: string,
): Promise<boolean> {
  const suppliedChecksum = (
    normalizeCallbackValue(
      payload.checksum,
    )
  );

  if (!suppliedChecksum) {
    return false;
  }

  const checksumPayload: Record<
    string,
    string
  > = {};

  for (
    const fieldName
    of CHECKSUM_FIELDS
  ) {
    checksumPayload[fieldName] = (
      normalizeCallbackValue(
        payload[fieldName],
      )
    );
  }

  const sortedKeys = (
    Object.keys(checksumPayload)
      .sort()
  );

  const checksumMessage = (
    sortedKeys
      .map(
        (key) => checksumPayload[key],
      )
      .join("|")
  );

  const expectedChecksum = (
    await createHmacSha256(
      apiSecretKey,
      checksumMessage,
    )
  );

  return constantTimeEquals(
    expectedChecksum,
    suppliedChecksum,
  );
}


function mapBayarCashStatus(
  status: unknown,
): PaymentStatus {
  const normalizedStatus = (
    Number(
      normalizeCallbackValue(status),
    )
  );

  switch (normalizedStatus) {
    case 0:
    case 1:
      return "PENDING";

    case 2:
      return "FAILED";

    case 3:
      return "PAID";

    case 4:
      return "CANCELLED";

    default:
      throw new Error(
        `Status BayarCash tidak dikenali: ${status}`,
      );
  }
}


function normalizeMoney(
  value: unknown,
): string {
  const parsedValue = Number(
    normalizeCallbackValue(value),
  );

  if (!Number.isFinite(parsedValue)) {
    throw new Error(
      "Amaun callback tidak sah.",
    );
  }

  return parsedValue.toFixed(2);
}


function getPlanDisplayName(
  planCode: string,
): string {
  switch (planCode.toUpperCase()) {
    case "STARTER":
      return "Starter";

    case "BUSINESS":
      return "Business";

    default:
      return planCode;
  }
}


function buildStatusUpdate(
  currentPayment: PaymentRecord,
  newStatus: PaymentStatus,
  payload: JsonObject,
): JsonObject {
  const currentTimestamp = (
    new Date().toISOString()
  );

  const updateData: JsonObject = {
    webhook_received_at: currentTimestamp,
    provider_payload: payload,
  };

  if (
    TERMINAL_SUCCESS_STATUSES.includes(
      currentPayment.status,
    )
    && newStatus !== "REFUNDED"
  ) {
    return updateData;
  }

  updateData.status = newStatus;

  if (newStatus === "PAID") {
    updateData.paid_at = (
      currentPayment.status === "PAID"
        ? undefined
        : currentTimestamp
    );
  }

  if (newStatus === "FAILED") {
    updateData.failed_at = currentTimestamp;
  }

  if (newStatus === "CANCELLED") {
    updateData.cancelled_at = (
      currentTimestamp
    );
  }

  return Object.fromEntries(
    Object.entries(updateData).filter(
      ([, value]) => value !== undefined,
    ),
  );
}


async function sendTelegramMessage(
  botToken: string,
  telegramId: number,
  message: string,
): Promise<void> {
  const telegramResponse = await fetch(
    `https://api.telegram.org/bot${botToken}/sendMessage`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        {
          chat_id: telegramId,
          text: message,
        },
      ),
    },
  );

  if (!telegramResponse.ok) {
    const responseText = (
      await telegramResponse.text()
    );

    throw new Error(
      "Telegram notification gagal: "
      + `${telegramResponse.status} `
      + responseText.slice(0, 300),
    );
  }
}


async function notifyPaymentResult(
  botToken: string | null,
  result: CallbackResult,
  amount: string,
  orderNumber: string,
): Promise<void> {
  if (!botToken) {
    console.warn(
      "TELEGRAM_BOT_TOKEN tidak tersedia. "
      + "Notifikasi Telegram dilangkau.",
    );
    return;
  }

  if (result.duplicate) {
    return;
  }

  const planName = getPlanDisplayName(
    result.plan_code,
  );

  let message: string;

  switch (result.payment_status) {
    case "PAID":
      message = (
        "✅ Pembayaran Berjaya\n\n"
        + `Nombor Tempahan: ${orderNumber}\n`
        + `Amaun: RM${amount}\n`
        + `Pelan: ${planName}\n\n`
        + "Subscription anda telah diaktifkan.\n\n"
        + "Gunakan /account untuk menyemak "
        + "status akaun."
      );
      break;

    case "FAILED":
      message = (
        "❌ Pembayaran Tidak Berjaya\n\n"
        + `Nombor Tempahan: ${orderNumber}\n`
        + `Amaun: RM${amount}\n`
        + `Pelan: ${planName}\n\n`
        + "Tiada perubahan dibuat pada "
        + "subscription anda.\n\n"
        + "Gunakan /upgrade untuk mencuba semula."
      );
      break;

    case "CANCELLED":
      message = (
        "⚠️ Pembayaran Dibatalkan\n\n"
        + `Nombor Tempahan: ${orderNumber}\n`
        + `Amaun: RM${amount}\n`
        + `Pelan: ${planName}\n\n`
        + "Tiada perubahan dibuat pada "
        + "subscription anda."
      );
      break;

    default:
      return;
  }

  try {
    await sendTelegramMessage(
      botToken,
      result.telegram_id,
      message,
    );
  } catch (error) {
    console.error(
      "Pembayaran sudah diproses tetapi "
      + "notifikasi Telegram gagal.",
      error,
    );
  }
}


async function findPaymentByOrderNumber(
  supabase: ReturnType<
    typeof createClient
  >,
  orderNumber: string,
): Promise<PaymentRecord> {
  const {
    data,
    error,
  } = await supabase
    .from("payments")
    .select(
      [
        "id",
        "payment_reference",
        "telegram_id",
        "plan_code",
        "provider_code",
        "provider_reference",
        "amount_rm",
        "currency_code",
        "status",
        "subscription_id",
        "customer_name",
        "metadata",
      ].join(","),
    )
    .eq(
      "provider_code",
      "BAYARCASH",
    )
    .contains(
      "metadata",
      {
        order_number: orderNumber,
      },
    )
    .order(
      "created_at",
      {
        ascending: false,
      },
    )
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(
      "Carian payment gagal: "
      + error.message,
    );
  }

  if (!data) {
    throw new Error(
      "Payment ReceiptBot tidak dijumpai "
      + `untuk order ${orderNumber}.`,
    );
  }

  return data as PaymentRecord;
}


async function activateSubscription(
  supabase: ReturnType<
    typeof createClient
  >,
  paymentReference: string,
): Promise<string | null> {
  const {
    data,
    error,
  } = await supabase.rpc(
    "activate_subscription_from_payment",
    {
      target_payment_reference: (
        paymentReference
      ),
    },
  );

  if (error) {
    throw new Error(
      "Pengaktifan subscription gagal: "
      + error.message,
    );
  }

  if (
    Array.isArray(data)
    && data.length > 0
  ) {
    const subscriptionId = (
      data[0]?.id
    );

    return subscriptionId
      ? String(subscriptionId)
      : null;
  }

  if (
    data
    && typeof data === "object"
    && "id" in data
  ) {
    const subscriptionId = (
      (data as JsonObject).id
    );

    return subscriptionId
      ? String(subscriptionId)
      : null;
  }

  return null;
}


async function processCallback(
  supabase: ReturnType<
    typeof createClient
  >,
  payload: JsonObject,
): Promise<CallbackResult> {
  const orderNumber = (
    normalizeCallbackValue(
      payload.order_number,
    )
  );

  if (!orderNumber) {
    throw new Error(
      "order_number tiada dalam callback.",
    );
  }

  const payment = (
    await findPaymentByOrderNumber(
      supabase,
      orderNumber,
    )
  );

  const callbackCurrency = (
    normalizeCallbackValue(
      payload.currency,
    ).toUpperCase()
  );

  if (
    callbackCurrency
    !== payment.currency_code.toUpperCase()
  ) {
    throw new Error(
      "Mata wang callback tidak sepadan.",
    );
  }

  const callbackAmount = normalizeMoney(
    payload.amount,
  );

  const paymentAmount = normalizeMoney(
    payment.amount_rm,
  );

  if (callbackAmount !== paymentAmount) {
    throw new Error(
      "Amaun callback tidak sepadan "
      + "dengan payment ReceiptBot.",
    );
  }

  const newStatus = mapBayarCashStatus(
    payload.status,
  );

  const duplicate = (
    payment.status === newStatus
    && (
      newStatus !== "PAID"
      || Boolean(payment.subscription_id)
    )
  );

  const updateData = buildStatusUpdate(
    payment,
    newStatus,
    payload,
  );

  const {
    data: updatedPayment,
    error: updateError,
  } = await supabase
    .from("payments")
    .update(updateData)
    .eq(
      "payment_reference",
      payment.payment_reference,
    )
    .select(
      [
        "payment_reference",
        "telegram_id",
        "plan_code",
        "status",
        "subscription_id",
      ].join(","),
    )
    .single();

  if (updateError) {
    throw new Error(
      "Kemas kini payment gagal: "
      + updateError.message,
    );
  }

  let subscriptionId = (
    updatedPayment.subscription_id
      ? String(
          updatedPayment.subscription_id,
        )
      : null
  );

  if (
    newStatus === "PAID"
    && !subscriptionId
  ) {
    subscriptionId = (
      await activateSubscription(
        supabase,
        payment.payment_reference,
      )
    );
  }

  return {
    payment_reference: (
      payment.payment_reference
    ),
    telegram_id: Number(
      payment.telegram_id,
    ),
    plan_code: String(
      payment.plan_code,
    ),
    payment_status: newStatus,
    subscription_id: subscriptionId,
    duplicate,
  };
}


Deno.serve(
  async (
    request: Request,
  ): Promise<Response> => {
    if (request.method === "GET") {
      return jsonResponse(
        {
          ok: true,
          service: "bayarcash-webhook",
          message: (
            "ReceiptBot BayarCash webhook aktif."
          ),
        },
      );
    }

    if (request.method !== "POST") {
      return jsonResponse(
        {
          ok: false,
          message: "Method tidak disokong.",
        },
        405,
      );
    }

    try {
      const supabaseUrl = (
        getRequiredEnvironmentVariable(
          "SUPABASE_URL",
        )
      );

      const supabaseServiceRoleKey = (
        getRequiredEnvironmentVariable(
          "SUPABASE_SERVICE_ROLE_KEY",
        )
      );

      const bayarCashApiSecretKey = (
        getRequiredEnvironmentVariable(
          "BAYARCASH_API_SECRET_KEY",
        )
      );

      const telegramBotToken = (
        Deno.env.get(
          "TELEGRAM_BOT_TOKEN",
        )?.trim()
        || null
      );

      const payload = (
        await parseRequestPayload(
          request,
        )
      );

      const checksumIsValid = (
        await verifyCallbackChecksum(
          payload,
          bayarCashApiSecretKey,
        )
      );

      if (!checksumIsValid) {
        console.error(
          "Checksum BayarCash tidak sah.",
          {
            order_number: (
              payload.order_number
            ),
            transaction_id: (
              payload.transaction_id
            ),
          },
        );

        return jsonResponse(
          {
            ok: false,
            message: "Checksum tidak sah.",
          },
          401,
        );
      }

      const supabase = createClient(
        supabaseUrl,
        supabaseServiceRoleKey,
        {
          auth: {
            persistSession: false,
            autoRefreshToken: false,
          },
        },
      );

      const result = await processCallback(
        supabase,
        payload,
      );

      const amount = normalizeMoney(
        payload.amount,
      );

      const orderNumber = (
        normalizeCallbackValue(
          payload.order_number,
        )
      );

      await notifyPaymentResult(
        telegramBotToken,
        result,
        amount,
        orderNumber,
      );

      console.log(
        "BayarCash callback berjaya diproses.",
        {
          order_number: orderNumber,
          payment_reference: (
            result.payment_reference
          ),
          status: result.payment_status,
          subscription_id: (
            result.subscription_id
          ),
          duplicate: result.duplicate,
        },
      );

      return jsonResponse(
        {
          ok: true,
          payment_reference: (
            result.payment_reference
          ),
          payment_status: (
            result.payment_status
          ),
          subscription_activated: Boolean(
            result.subscription_id,
          ),
          duplicate: result.duplicate,
        },
      );
    } catch (error) {
      const message = (
        error instanceof Error
          ? error.message
          : "Ralat webhook tidak diketahui."
      );

      console.error(
        "BayarCash webhook gagal.",
        error,
      );

      return jsonResponse(
        {
          ok: false,
          message,
        },
        500,
      );
    }
  },
);