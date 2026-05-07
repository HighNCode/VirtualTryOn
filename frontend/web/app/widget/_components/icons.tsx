import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number;
  color?: string;
  strokeWidth?: number;
};

function SvgIcon({
  size = 20,
  color = "currentColor",
  strokeWidth = 2,
  children,
  ...rest
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      {children}
    </svg>
  );
}

export function Search(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </SvgIcon>
  );
}

export function User(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c1.6-3.7 4.1-5 8-5s6.4 1.3 8 5" />
    </SvgIcon>
  );
}

export function ShoppingBag({ color = "currentColor", ...props }: IconProps) {
  return (
    <SvgIcon color={color} {...props}>
      <path d="M6 8h12l-1 12H7L6 8Z" />
      <path d="M9 9a3 3 0 1 1 6 0" />
    </SvgIcon>
  );
}

export function Minus(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M5 12h14" />
    </SvgIcon>
  );
}

export function Plus(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </SvgIcon>
  );
}

export function Camera(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <circle cx="12" cy="13.5" r="4" />
      <path d="M9 7l1.2-2h3.6L15 7" />
    </SvgIcon>
  );
}

export function ArrowRight(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </SvgIcon>
  );
}

export function X(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6 6 18" />
    </SvgIcon>
  );
}

export function Square(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="5" width="14" height="14" rx="2" />
    </SvgIcon>
  );
}

export function PersonStanding(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v6" />
      <path d="M8 11h8" />
      <path d="m10 13-2 6" />
      <path d="m14 13 2 6" />
    </SvgIcon>
  );
}

export function Maximize2(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M8 3H3v5" />
      <path d="m3 3 6 6" />
      <path d="M16 21h5v-5" />
      <path d="m21 21-6-6" />
      <path d="M21 8V3h-5" />
      <path d="m15 9 6-6" />
      <path d="M3 16v5h5" />
      <path d="m9 15-6 6" />
    </SvgIcon>
  );
}

export function Sun(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.9 4.9 1.4 1.4" />
      <path d="m17.7 17.7 1.4 1.4" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m4.9 19.1 1.4-1.4" />
      <path d="m17.7 6.3 1.4-1.4" />
    </SvgIcon>
  );
}

export function Upload(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 16V5" />
      <path d="m7 10 5-5 5 5" />
      <path d="M5 19h14" />
    </SvgIcon>
  );
}

export function CheckCircle2({ color = "#16a34a", ...props }: IconProps) {
  return (
    <SvgIcon color={color} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.2 2.2 4.8-4.8" />
    </SvgIcon>
  );
}

export function Circle(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
    </SvgIcon>
  );
}

export function RotateCcw(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </SvgIcon>
  );
}

export function TrendingUp(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="m3 17 6-6 4 4 7-8" />
      <path d="M14 7h6v6" />
    </SvgIcon>
  );
}

export function Ruler(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="m4 17 9-9 7 7-9 9-7-7Z" />
      <path d="m10 11 2 2" />
      <path d="m13 8 2 2" />
      <path d="m7 14 2 2" />
    </SvgIcon>
  );
}

export function Sparkles(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="m12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3Z" />
      <path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z" />
    </SvgIcon>
  );
}

export function ArrowLeft(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </SvgIcon>
  );
}

export function HelpCircle(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.9-2.5 2.2-2.5 4" />
      <circle cx="12" cy="17" r="0.8" fill="currentColor" stroke="none" />
    </SvgIcon>
  );
}

export function Lock(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 1 1 8 0v3" />
    </SvgIcon>
  );
}
