import { redirect } from "next/navigation";

// The upstream compete marketing landing (components/landing/*) is retained but
// not routed: the tracker opens straight into the product.
export default function Home() {
  redirect("/dashboard");
}
