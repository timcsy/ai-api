import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth";

export function HomePage() {
  const { member, logout } = useAuth();
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Hello, {member?.email}</CardTitle>
          <CardDescription>
            登入成功。業務頁面（用量、配額、目錄）將於 3b.1+ 加入。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" className="w-full" onClick={() => void logout()}>
            Logout
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
