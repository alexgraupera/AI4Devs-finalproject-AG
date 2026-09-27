import { useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "./icons";

type PhotoGalleryProps = {
  photos: string[];
  title: string;
  // `card`: one photo with arrows, as in a result. `detail`: a large photo and the thumbnails below.
  variant?: "card" | "detail";
  className?: string;
};

const arrowClass =
  "absolute top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-ink shadow-md transition-opacity hover:bg-white";

export function PhotoGallery({ photos, title, variant = "card", className = "" }: PhotoGalleryProps) {
  const [index, setIndex] = useState(0);
  const count = photos.length;
  const move = (step: number) => setIndex((current) => (current + step + count) % count);

  return (
    <div className={className}>
      <div className="group relative h-full overflow-hidden bg-canvas-sunken">
        <img
          src={photos[index]}
          alt={`${title}, foto ${index + 1} de ${count}`}
          loading={variant === "card" ? "lazy" : "eager"}
          className={`h-full w-full object-cover ${variant === "detail" ? "aspect-[16/10]" : "aspect-[4/3]"}`}
        />
        {count > 1 && (
          <>
            <button type="button" aria-label="Foto anterior" onClick={() => move(-1)} className={`${arrowClass} left-3`}>
              <ChevronLeftIcon className="size-5" />
            </button>
            <button type="button" aria-label="Foto siguiente" onClick={() => move(1)} className={`${arrowClass} right-3`}>
              <ChevronRightIcon className="size-5" />
            </button>
          </>
        )}
        <span className="absolute bottom-3 left-3 rounded-full bg-panel/80 px-2.5 py-1 text-xs font-medium text-panel-text">
          {index + 1} / {count}
        </span>
      </div>
      {variant === "detail" && count > 1 && (
        <div className="mt-3 grid grid-cols-5 gap-2">
          {photos.map((photo, position) => (
            <button
              key={photo}
              type="button"
              aria-label={`Ver foto ${position + 1}`}
              aria-current={position === index}
              onClick={() => setIndex(position)}
              className={`overflow-hidden rounded-lg border-2 ${position === index ? "border-accent" : "border-transparent opacity-80 hover:opacity-100"}`}
            >
              <img src={photo} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
