import "./widget.css";

export default function WidgetLayout({ children }: { children: React.ReactNode }) {
  return <div className="fixed inset-0 z-[200] bg-white overflow-auto">{children}</div>;
}
