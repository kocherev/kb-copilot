import { HomePage } from "@/components/home-page";

export default function Page() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return <HomePage apiUrl={apiUrl} />;
}
