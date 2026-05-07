"use client";

type PortalTopbarProps = {
  title: string;
  subtitle?: string;
};

export default function PortalTopbar({ title, subtitle }: PortalTopbarProps) {
  const today = new Date().toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric"
  });

  return (
    <header className="portal-topbar">
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      <span className="portal-topbar-date">{today}</span>
    </header>
  );
}
