const GLYPH_CENTER_X = 11.01;
const GLYPH_CENTER_Y = 12;
const GLYPH_SCALE = 0.68;

const GithubIcon = ({
  size = undefined,
  color = "#ffffff",
  strokeWidth = 2,
  background = "#000000",
  borderColor = "#000000",
  borderWidth = 1,
  opacity = 1,
  rotation = 0,
  shadow = 0,
  flipHorizontal = false,
  flipVertical = false,
  padding = 0,
}) => {
  const transforms = [];
  if (rotation !== 0) transforms.push(`rotate(${rotation}deg)`);
  if (flipHorizontal) transforms.push("scaleX(-1)");
  if (flipVertical) transforms.push("scaleY(-1)");

  const radius = 12 - padding - borderWidth / 2;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        opacity,
        transform: transforms.join(" ") || undefined,
        filter:
          shadow > 0
            ? `drop-shadow(0 ${shadow}px ${shadow * 2}px rgba(0,0,0,0.3))`
            : undefined,
      }}
    >
      <circle
        cx={12}
        cy={12}
        r={radius}
        fill={background}
        stroke={borderColor}
        strokeWidth={borderWidth}
      />
      <g
        transform={`translate(12 12) scale(${GLYPH_SCALE}) translate(${-GLYPH_CENTER_X} ${-GLYPH_CENTER_Y})`}
        strokeWidth={strokeWidth / GLYPH_SCALE}
      >
        <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5c.08-1.25-.27-2.48-1-3.5c.28-1.15.28-2.35 0-3.5c0 0-1 0-3 1.5c-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5c-.39.49-.68 1.05-.85 1.65S8.93 17.38 9 18v4" />
        <path d="M9 18c-4.51 2-5-2-7-2" />
      </g>
    </svg>
  );
};

export default GithubIcon;
