import AgentClient from "../../components/AgentClient";
import { AuthGate } from "../../components/AuthGate";
import "./agent.css";

export default function AgentPage() {
  return <AuthGate><AgentClient /></AuthGate>;
}
