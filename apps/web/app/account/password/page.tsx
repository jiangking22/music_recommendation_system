import AuthForm from "../../../components/AuthForm";
import { AuthGate } from "../../../components/AuthGate";
export default function PasswordPage() { return <AuthGate><AuthForm mode="password" /></AuthGate>; }
