export function GET(): Response {
  return Response.json({ status: "ok", service: "mnemos-web" });
}
