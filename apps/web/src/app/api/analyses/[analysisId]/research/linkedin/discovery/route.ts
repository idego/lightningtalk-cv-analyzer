import { proxyLinkedInResearch } from "../proxy";
export async function POST(req: Request, context: { params: Promise<{ analysisId: string }> }) { return proxyLinkedInResearch(req, context); }
