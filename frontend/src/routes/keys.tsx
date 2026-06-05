import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiEndpointCard } from "@/components/api-endpoint-card";
import { AppCredentialsCard } from "@/components/app-credentials-card";
import { CodexInstallCard } from "@/components/codex-install-card";
import { useAuth } from "@/contexts/auth";

export function KeysPage() {
  const { member } = useAuth();
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
        <CodexInstallCard baseUrl={member?.gateway_base_url ?? window.location.origin} />
      </section>

      <section>
        <AppCredentialsCard />
      </section>
    </div>
  );
}
