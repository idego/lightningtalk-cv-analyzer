import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function AnalyzePlaceholderPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold">Analyze</h2>
        <Badge variant="secondary">Placeholder</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Frontend shell is ready</CardTitle>
          <CardDescription>
            Issue #3 delivers the visual admin foundation. Authentication and upload workflows are added in issues #4 and #5.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          This page will host CV upload and explainable results once the next stacked branches land.
        </CardContent>
      </Card>
    </div>
  );
}
