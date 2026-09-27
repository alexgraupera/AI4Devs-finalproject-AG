import { useEffect, useState } from "react";
import { serviceStatus } from "../api/client";

export const WAKING_UP =
  "Conectando con el servicio... Si nadie lo ha usado en los últimos 15 minutos, el plan gratuito lo ha dormido y tarda hasta un minuto en despertar.";
export const SERVICE_DOWN = "El servicio no responde ahora mismo. Vuelve a intentarlo en unos minutos.";

/**
 * Asks whether the API is up as soon as a tool is on screen, so a sleeping free-tier API starts
 * waking while the person is still reading. It says so only if the answer takes a while: an awake
 * API answers before the notice would flash.
 */
export function ServiceBanner({ noticeAfterMs = 800 }: { noticeAfterMs?: number }) {
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => active && setSlow(true), noticeAfterMs);
    serviceStatus().then((answer) => {
      if (active) setStatus(answer);
    });
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [noticeAfterMs]);

  if (status === "down") {
    return (
      <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
        {SERVICE_DOWN}
      </p>
    );
  }
  if (status === "checking" && slow) {
    return (
      <p role="status" className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
        {WAKING_UP}
      </p>
    );
  }
  return null;
}
