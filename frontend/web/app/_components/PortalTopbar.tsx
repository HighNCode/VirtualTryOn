"use client";

type PortalTopbarProps = {
  title: string;
  subtitle?: string;
};

export default function PortalTopbar({ title, subtitle }: PortalTopbarProps) {
  const today = new Date().toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <header
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "18px 28px", background: "#fff", borderBottom: "1px solid #f0f0f0",
        flexShrink: 0,
      }}
    >
      <div>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, lineHeight: 1.2, color: "#1a1a1a" }}>
          {title}
        </h2>
        {subtitle ? (
          <p style={{ margin: "2px 0 0", fontSize: 14, color: "#6b7280" }}>{subtitle}</p>
        ) : null}
      </div>
      <span
        style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 500, background: "rgba(126, 1, 117, 0.07)", color: "#7E0175" }}
      >
        {today}
      </span>
    </header>
  );
}
