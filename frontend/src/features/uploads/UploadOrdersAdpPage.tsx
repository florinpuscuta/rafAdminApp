import UploadOrdersPage from "./UploadOrdersPage";

export default function UploadOrdersAdpPage() {
  return (
    <UploadOrdersPage
      source="adp"
      title="Upload Comenzi Open (ADP)"
      subtitle='Încarcă Excel-ul "radComenzi" Adeplast (sheet-uri per lanț: Dedeman, Altex, Leroy Merlin, Hornbach). Fiecare rând intră ca NELIVRAT sau NEFACTURAT pentru data snapshot-ului. Re-upload aceeași zi = replace doar acea zi.'
    />
  );
}
