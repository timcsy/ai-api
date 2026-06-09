import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiEndpointCard } from "@/components/api-endpoint-card";
import { AppCredentialsCard } from "@/components/app-credentials-card";

export function KeysPage() {
  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">金鑰</h1>
        <Alert className="mt-3">
          <AlertDescription>
            <strong>分配</strong>＝你能用哪些模型；<strong>金鑰</strong>＝拿來連線的鑰匙。
          </AlertDescription>
        </Alert>
      </section>

      <section className="space-y-3">
        <ApiEndpointCard />
      </section>

      <section>
        <AppCredentialsCard />
      </section>
    </div>
  );
}
