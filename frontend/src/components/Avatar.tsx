import { avatarColor, initials } from "@/lib/format";

const SIZES = {
  sm: "h-7 w-7 text-[11px]",
  md: "h-10 w-10 text-sm",
  lg: "h-14 w-14 text-lg",
};

export function Avatar({
  name,
  index,
  size = "md",
  className = "",
}: {
  name: string;
  index: number;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      title={name}
      className={`inline-flex items-center justify-center rounded-full font-semibold ring-2 ring-white ${SIZES[size]} ${avatarColor(index)} ${className}`}
    >
      {initials(name)}
    </span>
  );
}

export function AvatarStack({ names, indexOf, size = "sm" }: {
  names: string[];
  indexOf: (name: string) => number;
  size?: keyof typeof SIZES;
}) {
  return (
    <span className="flex -space-x-2">
      {names.map((n) => (
        <Avatar key={n} name={n} index={indexOf(n)} size={size} />
      ))}
    </span>
  );
}
