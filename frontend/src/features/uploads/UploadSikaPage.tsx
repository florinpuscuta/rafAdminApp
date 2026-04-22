import UploadAdpPage from "./UploadAdpPage";

export default function UploadSikaPage() {
  return (
    <UploadAdpPage
      source="sika"
      title="Upload Date Brute (SIKA)"
      subtitle='Încarcă Excel-ul Sika DIY (un sheet per lună — "IAN 26", "FEB 26", etc). Fiecare rând aduce vânzări pentru 2 ani (year-1 + year curent). Mapare agent/magazin se rezolvă automat din Raf mapping pe cod ship-to (primar) sau nume (fallback). Rândurile ADP nu sunt afectate.'
    />
  );
}
