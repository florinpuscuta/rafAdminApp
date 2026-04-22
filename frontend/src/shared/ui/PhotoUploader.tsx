/**
 * PhotoUploader — componentă reutilizabilă pentru upload poze.
 *
 * Două butoane (ca în legacy `galleryUploadFiles`):
 *   📷 Fotografiază — deschide camera pe mobil (capture="environment")
 *   📤 Alege fișiere — picker standard (galerie/folder, multiple)
 *
 * Agentul poate să pozeze cu telefonul sau să importe poze existente.
 */
import { useRef } from "react";

export interface PhotoUploaderProps {
  onFiles: (files: FileList) => void | Promise<void>;
  disabled?: boolean;
  status?: string | null;
  compact?: boolean;  // buton mic (pt. detail pages)
  accept?: string;
}

export function PhotoUploader({
  onFiles, disabled = false, status, compact = false, accept = "image/*",
}: PhotoUploaderProps) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLInputElement>(null);

  const handleCamera = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) onFiles(e.target.files);
    if (cameraRef.current) cameraRef.current.value = "";
  };
  const handlePicker = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) onFiles(e.target.files);
    if (pickerRef.current) pickerRef.current.value = "";
  };

  const size = compact ? "6px 10px" : "8px 12px";
  const fontSize = compact ? 12 : 13;
  const labelBase: React.CSSProperties = {
    padding: size, borderRadius: 8, border: "none", cursor: "pointer",
    color: "#fff", fontWeight: 600,
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
    fontSize, opacity: disabled ? 0.5 : 1,
    flex: "1 1 0", minWidth: 0, whiteSpace: "nowrap",
    minHeight: 36,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{
        display: "flex", gap: 8, alignItems: "stretch",
        flexWrap: "nowrap",
      }}>
        <label style={{ ...labelBase, background: "#25D366" }}
          title="Fotografiază direct cu camera telefonului">
          📷 Fotografiază
          <input
            ref={cameraRef}
            type="file"
            accept={accept}
            capture="environment"
            style={{ display: "none" }}
            onChange={handleCamera}
            disabled={disabled}
          />
        </label>
        <label style={{ ...labelBase, background: "var(--accent)" }}
          title="Alege poze din galerie sau dintr-un folder">
          📤 Alege fișiere
          <input
            ref={pickerRef}
            type="file"
            accept={accept}
            multiple
            style={{ display: "none" }}
            onChange={handlePicker}
            disabled={disabled}
          />
        </label>
      </div>
      {status && (
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{status}</span>
      )}
    </div>
  );
}
