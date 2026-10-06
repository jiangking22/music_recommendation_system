import ProductClient from "../components/ProductClient";
import { AuthGate } from "../components/AuthGate";

export default function Home() {
  return <AuthGate><ProductClient /></AuthGate>;
}
