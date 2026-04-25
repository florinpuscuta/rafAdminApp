import { type ReactNode } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { ToastProvider } from "./shared/ui/ToastProvider";
import { AuthProvider, useAuth } from "./features/auth/AuthContext";
import AgentDetailPage from "./features/agents/AgentDetailPage";
import AgentsPage from "./features/agents/AgentsPage";
import UnmappedAgentsPage from "./features/agents/UnmappedAgentsPage";
import ApiKeysPage from "./features/api-keys/ApiKeysPage";
import AssignmentsPage from "./features/assignments/AssignmentsPage";
import AuditLogsPage from "./features/audit/AuditLogsPage";
import AcceptInvitePage from "./features/auth/AcceptInvitePage";
import EmailVerifyBanner from "./features/auth/EmailVerifyBanner";
import ForgotPasswordPage from "./features/auth/ForgotPasswordPage";
import LoginPage from "./features/auth/LoginPage";
import ResetPasswordPage from "./features/auth/ResetPasswordPage";
import SignupPage from "./features/auth/SignupPage";
import VerifyEmailPage from "./features/auth/VerifyEmailPage";
import ChatPage from "./features/ai/ChatPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import ConsolidatPage from "./features/consolidat/ConsolidatPage";
import EpsDetailsPage from "./features/eps/EpsDetailsPage";
import DiscountRulesPage from "./features/discountrules/DiscountRulesPage";
import MarginePage from "./features/margine/MarginePage";
import MarjaLunaraPage from "./features/marjalunara/MarjaLunaraPage";
import PretProductiePage from "./features/pretproductie/PretProductiePage";
import UploadAdpPage from "./features/uploads/UploadAdpPage";
import UploadOrdersAdpPage from "./features/uploads/UploadOrdersAdpPage";
import UploadOrdersSikaPage from "./features/uploads/UploadOrdersSikaPage";
import UploadSikaPage from "./features/uploads/UploadSikaPage";
import UploadSikaMtdPage from "./features/uploads/UploadSikaMtdPage";
import VzLaZiPage from "./features/vzlazi/VzLaZiPage";
import TopMagazinePage from "./features/topmagazine/TopMagazinePage";
import CookieConsent from "./features/legal/CookieConsent";
import PrivacyPage from "./features/legal/PrivacyPage";
import TermsPage from "./features/legal/TermsPage";
import GalleryPage from "./features/gallery/GalleryPage";
import ActivitatePage from "./features/activitate/ActivitatePage";
import AnalizaMagazinPage from "./features/analizamagazin/AnalizaMagazinPage";
import AnalizaMagazinDashboardPage from "./features/analizamagazindashboard/AnalizaMagazinDashboardPage";
import AnalizaPeLuniPage from "./features/analizapeluni/AnalizaPeLuniPage";
import BonusariPage from "./features/bonusari/BonusariPage";
import EvaluareHubPage from "./features/evaluareagenti/EvaluareHubPage";
import SalFixPage from "./features/evaluareagenti/SalFixPage";
import InputLunarAgentPage from "./features/evaluareagenti/InputLunarAgentPage";
import ZonaAgentPage from "./features/evaluareagenti/ZonaAgentPage";
import AgentAnualPage from "./features/evaluareagenti/AgentAnualPage";
import CostAnualPage from "./features/evaluareagenti/CostAnualPage";
import DashboardAgentiPage from "./features/evaluareagenti/DashboardAgentiPage";
import PodiumAgentiPage from "./features/evaluareagenti/PodiumAgentiPage";
import FacturiBonusAsignatPage from "./features/evaluareagenti/FacturiBonusAsignatPage";
import ComenziFaraIndPage from "./features/comenzifaraind/ComenziFaraIndPage";
import GrupeProdusePage from "./features/grupeproduse/GrupeProdusePage";
import ArboreProdusePage from "./features/arboreproduse/ArboreProdusePage";
import ArboreClientiPage from "./features/arboreproduse/ArboreClientiPage";
import MarcaPrivataPage from "./features/marcaprivata/MarcaPrivataPage";
import MktCatalogPage from "./features/mktcatalog/MktCatalogPage";
import MktConcurentaPage from "./features/mktconcurenta/MktConcurentaPage";
import MktFacingPage from "./features/mktfacing/MktFacingPage";
import DashFaceTrackerPage from "./features/dashfacetracker/DashFaceTrackerPage";
import FacingConfigPage from "./features/facingconfig/FacingConfigPage";
import MktPanouriPage from "./features/mktpanouri/MktPanouriPage";
import MktSikaPage from "./features/mktsika/MktSikaPage";
import ApprovalsPage from "./features/approvals/ApprovalsPage";
import MortarePage from "./features/mortare/MortarePage";
import ParcursPage from "./features/parcurs/ParcursPage";
import ProblemePage from "./features/probleme/ProblemePage";
import PrognozaPage from "./features/prognoza/PrognozaPage";
import RapoartLunarPage from "./features/rapoartlunar/RapoartLunarPage";
import RapoartWordPage from "./features/rapoartword/RapoartWordPage";
import TarghetPage from "./features/targhet/TarghetPage";
import TaskuriPage from "./features/taskuri/TaskuriPage";
import TopProdusePage from "./features/topproduse/TopProdusePage";
import AllocateAgentsPage from "./features/mappings/AllocateAgentsPage";
import MappingsPage from "./features/mappings/MappingsPage";
import Pret3NetPage from "./features/pret3net/Pret3NetPage";
import PreturiKaRetailPage from "./features/preturikaretail/PreturiKaRetailPage";
import PreturiOwnKaPage from "./features/preturiownka/PreturiOwnKaPage";
import PreturiComparativePage from "./features/preturicomparative/PreturiComparativePage";
import AiKeysPage from "./features/aisettings/AiKeysPage";
import AppearancePage from "./features/aisettings/AppearancePage";
import PropuneriKaListarePage from "./features/propunerikalistare/PropuneriKaListarePage";
import KaVsTtPage from "./features/prices/KaVsTtPage";
import ProductDetailPage from "./features/products/ProductDetailPage";
import ProductsPage from "./features/products/ProductsPage";
import UnmappedProductsPage from "./features/products/UnmappedProductsPage";
import SalesPage from "./features/sales/SalesPage";
import StoreDetailPage from "./features/stores/StoreDetailPage";
import StoresPage from "./features/stores/StoresPage";
import UnmappedStoresPage from "./features/stores/UnmappedStoresPage";
import TenantSettingsPage from "./features/tenants/TenantSettingsPage";
import UsersPage from "./features/users/UsersPage";
import ComingSoonPage from "./shared/ui/ComingSoonPage";
import { CompanyScopeProvider, useCompanyScope } from "./shared/ui/CompanyScopeProvider";
import { ConfirmProvider } from "./shared/ui/ConfirmDialog";
import { ErrorBoundary } from "./shared/ui/ErrorBoundary";
import { RouteBoundary } from "./shared/ui/RouteBoundary";
import { Shell } from "./shared/ui/Shell";
import { PrivacyProvider } from "./shared/ui/PrivacyProvider";
import { ThemeProvider } from "./shared/ui/ThemeProvider";

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
       <PrivacyProvider>
        <CompanyScopeProvider>
          <ToastProvider>
            <ConfirmProvider>
              <ErrorBoundary name="root">
                <AuthProvider>
                  <CookieConsent />
                  <Routes>
                    <Route path="/login" element={<RouteBoundary name="login"><LoginPage /></RouteBoundary>} />
                    <Route path="/signup" element={<RouteBoundary name="signup"><SignupPage /></RouteBoundary>} />
                    <Route path="/privacy" element={<RouteBoundary name="privacy"><PrivacyPage /></RouteBoundary>} />
                    <Route path="/terms" element={<RouteBoundary name="terms"><TermsPage /></RouteBoundary>} />
                    <Route path="/forgot-password" element={<RouteBoundary name="forgot-password"><ForgotPasswordPage /></RouteBoundary>} />
                    <Route path="/reset-password" element={<RouteBoundary name="reset-password"><ResetPasswordPage /></RouteBoundary>} />
                    <Route path="/verify-email" element={<RouteBoundary name="verify-email"><VerifyEmailPage /></RouteBoundary>} />
                    <Route path="/accept-invite" element={<RouteBoundary name="accept-invite"><AcceptInvitePage /></RouteBoundary>} />
                    <Route
                      path="/*"
                      element={
                        <RequireAuth>
                          <AuthedShell />
                        </RequireAuth>
                      }
                    />
                  </Routes>
                </AuthProvider>
              </ErrorBoundary>
            </ConfirmProvider>
          </ToastProvider>
        </CompanyScopeProvider>
       </PrivacyProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p style={{ padding: 24 }}>Se încarcă…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <>{children}</>;
}

function NoSikadp({ children }: { children: ReactNode }) {
  const { scope } = useCompanyScope();
  if (scope === "sikadp") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function SikadpOnly({ children }: { children: ReactNode }) {
  const { scope } = useCompanyScope();
  if (scope !== "sikadp") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AuthedShell() {
  return (
    <>
      <ImpersonationBanner />
      <EmailVerifyBanner />
      <Shell>
        <Routes>
          <Route path="/" element={<RouteBoundary name="dashboard"><DashboardPage /></RouteBoundary>} />
          <Route path="/sales" element={<RouteBoundary name="sales"><SalesPage /></RouteBoundary>} />
          <Route path="/consolidat" element={<RouteBoundary name="consolidat"><ConsolidatPage /></RouteBoundary>} />
          <Route path="/gallery" element={<RouteBoundary name="gallery"><GalleryPage /></RouteBoundary>} />
          <Route path="/prices/ka-vs-tt" element={<NoSikadp><RouteBoundary name="prices-ka-tt"><KaVsTtPage /></RouteBoundary></NoSikadp>} />
          <Route path="/chat" element={<RouteBoundary name="chat"><ChatPage /></RouteBoundary>} />
          <Route path="/stores" element={<RouteBoundary name="stores"><StoresPage /></RouteBoundary>} />
          <Route path="/stores/:id" element={<RouteBoundary name="store-detail"><StoreDetailPage /></RouteBoundary>} />
          <Route path="/agents" element={<RouteBoundary name="agents"><AgentsPage /></RouteBoundary>} />
          <Route path="/agents/:id" element={<RouteBoundary name="agent-detail"><AgentDetailPage /></RouteBoundary>} />
          <Route path="/products" element={<RouteBoundary name="products"><ProductsPage /></RouteBoundary>} />
          <Route path="/products/:id" element={<RouteBoundary name="product-detail"><ProductDetailPage /></RouteBoundary>} />
          <Route path="/assignments" element={<RouteBoundary name="assignments"><AssignmentsPage /></RouteBoundary>} />
          <Route path="/unmapped/stores" element={<RouteBoundary name="unmapped-stores"><UnmappedStoresPage /></RouteBoundary>} />
          <Route path="/unmapped/agents" element={<RouteBoundary name="unmapped-agents"><UnmappedAgentsPage /></RouteBoundary>} />
          <Route path="/unmapped/products" element={<RouteBoundary name="unmapped-products"><UnmappedProductsPage /></RouteBoundary>} />
          <Route path="/users" element={<RouteBoundary name="users"><UsersPage /></RouteBoundary>} />
          <Route path="/audit-logs" element={<RouteBoundary name="audit-logs"><AuditLogsPage /></RouteBoundary>} />
          <Route path="/api-keys" element={<RouteBoundary name="api-keys"><ApiKeysPage /></RouteBoundary>} />
          <Route path="/settings" element={<RouteBoundary name="settings"><TenantSettingsPage /></RouteBoundary>} />

          {/* Legacy feature placeholders — migrate incremental. Structurate
              după meniurile legacy: Analiza / Marketing / Rapoarte / Targhet
              / Taskuri / Probleme / Grupe / Top / Mortar / EPS / PrivateLabel
              / Preturi / Forecast / Settings Upload. */}
          <Route path="/analiza/luni" element={<RouteBoundary name="analiza-luni"><AnalizaPeLuniPage /></RouteBoundary>} />
          <Route path="/analiza/magazin" element={<NoSikadp><RouteBoundary name="analiza-magazin"><AnalizaMagazinPage /></RouteBoundary></NoSikadp>} />
          <Route path="/analiza/magazin-dashboard" element={<NoSikadp><RouteBoundary name="analiza-magazin-dashboard"><AnalizaMagazinDashboardPage /></RouteBoundary></NoSikadp>} />
          <Route path="/analiza/zi" element={<RouteBoundary name="analiza-zi"><VzLaZiPage /></RouteBoundary>} />
          <Route path="/analiza/comenzi" element={<RouteBoundary name="analiza-comenzi"><ComenziFaraIndPage /></RouteBoundary>} />
          <Route path="/analiza/top-magazine" element={<RouteBoundary name="top-magazine"><TopMagazinePage /></RouteBoundary>} />
          <Route path="/marketing/concurenta" element={<RouteBoundary name="marketing-concurenta"><MktConcurentaPage /></RouteBoundary>} />
          <Route path="/marketing/catalog" element={<RouteBoundary name="marketing-catalog"><MktCatalogPage /></RouteBoundary>} />
          <Route path="/marketing/facing" element={<RouteBoundary name="marketing-facing"><MktFacingPage /></RouteBoundary>} />
          <Route path="/marketing/dash-face" element={<RouteBoundary name="marketing-dash-face"><DashFaceTrackerPage /></RouteBoundary>} />
          <Route path="/marketing/facing-config" element={<RouteBoundary name="marketing-facing-config"><FacingConfigPage /></RouteBoundary>} />
          <Route path="/marketing/panouri" element={<RouteBoundary name="marketing-panouri"><MktPanouriPage /></RouteBoundary>} />
          <Route path="/aprobari" element={<RouteBoundary name="aprobari"><ApprovalsPage /></RouteBoundary>} />
          <Route path="/marketing/sika" element={<RouteBoundary name="marketing-sika"><MktSikaPage /></RouteBoundary>} />
          <Route path="/rapoarte/word" element={<RouteBoundary name="rapoarte-word"><RapoartWordPage /></RouteBoundary>} />
          <Route path="/rapoarte/lunar" element={<RouteBoundary name="rapoarte-lunar"><RapoartLunarPage /></RouteBoundary>} />
          <Route path="/targhet" element={<RouteBoundary name="targhet"><TarghetPage /></RouteBoundary>} />
          <Route path="/bonusari" element={<RouteBoundary name="bonusari"><BonusariPage /></RouteBoundary>} />
          <Route path="/taskuri" element={<RouteBoundary name="taskuri"><TaskuriPage /></RouteBoundary>} />
          <Route path="/parcurs" element={<RouteBoundary name="parcurs"><ParcursPage /></RouteBoundary>} />
          <Route path="/activitate" element={<RouteBoundary name="activitate"><ActivitatePage /></RouteBoundary>} />
          <Route path="/probleme/:period" element={<RouteBoundary name="probleme"><ProblemePage /></RouteBoundary>} />
          <Route path="/grupe-arbore" element={<RouteBoundary name="grupe-arbore"><ArboreProdusePage /></RouteBoundary>} />
          <Route path="/grupe-arbore-clienti" element={<RouteBoundary name="grupe-arbore-clienti"><ArboreClientiPage /></RouteBoundary>} />
          <Route path="/grupe/:group" element={<RouteBoundary name="grupe"><GrupeProdusePage /></RouteBoundary>} />
          <Route path="/topprod/:group" element={<RouteBoundary name="topprod"><TopProdusePage /></RouteBoundary>} />
          <Route path="/mortar" element={<RouteBoundary name="mortar"><MortarePage /></RouteBoundary>} />
          <Route path="/eps" element={<RouteBoundary name="eps"><EpsDetailsPage /></RouteBoundary>} />
          <Route path="/privatelabel" element={<RouteBoundary name="privatelabel"><MarcaPrivataPage /></RouteBoundary>} />
          <Route path="/prices/own" element={<NoSikadp><RouteBoundary name="prices-own"><PreturiOwnKaPage /></RouteBoundary></NoSikadp>} />
          <Route path="/prices/comparative" element={<NoSikadp><RouteBoundary name="prices-comparative"><PreturiComparativePage /></RouteBoundary></NoSikadp>} />
          <Route path="/prices/pret3net" element={<NoSikadp><RouteBoundary name="prices-pret3net"><Pret3NetPage /></RouteBoundary></NoSikadp>} />
          <Route path="/prices/propuneri" element={<NoSikadp><RouteBoundary name="prices-propuneri"><PropuneriKaListarePage /></RouteBoundary></NoSikadp>} />
          <Route path="/prices/ka-retail" element={<NoSikadp><RouteBoundary name="prices-ka-retail"><PreturiKaRetailPage /></RouteBoundary></NoSikadp>} />
          <Route path="/forecast" element={<RouteBoundary name="forecast"><PrognozaPage /></RouteBoundary>} />
          <Route path="/settings/upload-adp" element={<RouteBoundary name="settings-upload-adp"><UploadAdpPage /></RouteBoundary>} />
          <Route path="/settings/upload-sika" element={<RouteBoundary name="settings-upload-sika"><UploadSikaPage /></RouteBoundary>} />
          <Route path="/settings/upload-sika-mtd" element={<RouteBoundary name="settings-upload-sika-mtd"><UploadSikaMtdPage /></RouteBoundary>} />
          <Route path="/settings/upload-orders-adp" element={<RouteBoundary name="settings-upload-orders-adp"><UploadOrdersAdpPage /></RouteBoundary>} />
          <Route path="/settings/upload-orders-sika" element={<RouteBoundary name="settings-upload-orders-sika"><UploadOrdersSikaPage /></RouteBoundary>} />
          <Route path="/settings/pret-productie" element={<RouteBoundary name="settings-pret-productie"><PretProductiePage /></RouteBoundary>} />
          <Route path="/analiza/margine" element={<RouteBoundary name="analiza-margine"><MarginePage /></RouteBoundary>} />
          <Route path="/analiza/marja-lunara" element={<RouteBoundary name="analiza-marja-lunara"><MarjaLunaraPage /></RouteBoundary>} />
          <Route path="/settings/discount-rules" element={<RouteBoundary name="settings-discount-rules"><DiscountRulesPage /></RouteBoundary>} />
          <Route path="/settings/mappings" element={<RouteBoundary name="settings-mappings"><MappingsPage /></RouteBoundary>} />
          <Route path="/settings/allocate-agents" element={<RouteBoundary name="settings-allocate-agents"><AllocateAgentsPage /></RouteBoundary>} />
          <Route path="/settings/ai-keys" element={<RouteBoundary name="settings-ai-keys"><AiKeysPage /></RouteBoundary>} />
          <Route path="/settings/appearance" element={<RouteBoundary name="settings-appearance"><AppearancePage /></RouteBoundary>} />
          <Route path="/coming-soon/config" element={<RouteBoundary name="coming-soon-config"><ComingSoonPage title="De configurat" /></RouteBoundary>} />

          {/* Evaluare — SIKADP only. Un hub cu două grupe: Input Date & Analiza. */}
          <Route path="/evaluare" element={<SikadpOnly><RouteBoundary name="evaluare"><EvaluareHubPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/sal-fix" element={<SikadpOnly><RouteBoundary name="evaluare-sal-fix"><SalFixPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/input-lunar" element={<SikadpOnly><RouteBoundary name="evaluare-input"><InputLunarAgentPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/zona-agent" element={<SikadpOnly><RouteBoundary name="evaluare-zona-agent"><ZonaAgentPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/cost-anual" element={<SikadpOnly><RouteBoundary name="evaluare-cost-anual"><CostAnualPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/agent-anual" element={<SikadpOnly><RouteBoundary name="evaluare-agent-anual"><AgentAnualPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/dashboard" element={<SikadpOnly><RouteBoundary name="evaluare-dashboard"><DashboardAgentiPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/podium" element={<SikadpOnly><RouteBoundary name="evaluare-podium"><PodiumAgentiPage /></RouteBoundary></SikadpOnly>} />
          <Route path="/evaluare/facturi-bonus" element={<SikadpOnly><RouteBoundary name="evaluare-facturi-bonus"><FacturiBonusAsignatPage /></RouteBoundary></SikadpOnly>} />
        </Routes>
      </Shell>
    </>
  );
}

function ImpersonationBanner() {
  const email = sessionStorage.getItem("adeplast_impersonating");
  if (!email) return null;
  function exit() {
    sessionStorage.removeItem("adeplast_impersonating");
    import("./shared/api").then(({ clearAuth }) => {
      clearAuth();
      window.location.href = "/login";
    });
  }
  return (
    <div style={{
      padding: "6px 16px", background: "#fef3c7", borderBottom: "1px solid #f0c674",
      fontSize: 13, display: "flex", justifyContent: "space-between", alignItems: "center",
      color: "#1f2937",
    }}>
      <span>
        🎭 <strong>Vezi ca</strong> <code>{email}</code> (impersonare activă · 30 min)
      </span>
      <button onClick={exit} style={{
        padding: "3px 10px", fontSize: 12, cursor: "pointer",
        background: "#fff", border: "1px solid #c0a050", borderRadius: 3,
      }}>
        Ieși din impersonare
      </button>
    </div>
  );
}
