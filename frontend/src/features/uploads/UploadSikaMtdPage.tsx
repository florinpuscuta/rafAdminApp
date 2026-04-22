import UploadAdpPage from "./UploadAdpPage";

export default function UploadSikaMtdPage() {
  return (
    <UploadAdpPage
      source="sika_mtd"
      title="Upload Vz MTD (SIKA) — luna curentă"
      subtitle='Încarcă "Raport vânzări ship-to party DIY DD.MM.YYYY" (un sheet, header cu Net Sales pentru luna curentă + același luna an anterior). Folosit DOAR pentru Vz la zi Sika (luna curentă încă neacoperită de importul principal Sika). Re-upload = replace pentru aceleași (an, lună). Rândurile importului Sika principal NU sunt afectate.'
    />
  );
}
