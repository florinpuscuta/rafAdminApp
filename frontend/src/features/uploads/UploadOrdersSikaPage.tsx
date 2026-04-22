import UploadOrdersPage from "./UploadOrdersPage";

export default function UploadOrdersSikaPage() {
  return (
    <UploadOrdersPage
      source="sika"
      title="Upload Comenzi Open (SIKA)"
      subtitle="Încarcă Excel-ul cu comenzi open Sika (un sheet, col Client/Ship-to/Material/Open Qty/Open Amount). Toate rândurile intră ca OPEN pentru data snapshot-ului. Re-upload aceeași zi = replace doar acea zi."
    />
  );
}
