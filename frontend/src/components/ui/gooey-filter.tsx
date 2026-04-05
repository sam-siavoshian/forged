const GOOEY_FILTER_ID = 'gooey-filter-pixel-trail';

function GooeyFilter({
  id = GOOEY_FILTER_ID,
  strength = 10,
}: {
  id?: string;
  strength?: number;
}) {
  return (
    <svg className="pointer-events-none absolute h-0 w-0 overflow-hidden" aria-hidden>
      <defs>
        <filter id={id}>
          <feGaussianBlur in="SourceGraphic" stdDeviation={strength} result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9"
            result="goo"
          />
          <feComposite in="SourceGraphic" in2="goo" operator="atop" />
        </filter>
      </defs>
    </svg>
  );
}

export { GooeyFilter, GOOEY_FILTER_ID };
