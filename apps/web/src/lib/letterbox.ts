export type Size = { width: number; height: number };
export type Box = { left: number; top: number; width: number; height: number };

// Where an object-contain video lands inside its container, in container pixels.
export function letterbox(container: Size, video: Size): Box {
  if (video.width <= 0 || video.height <= 0) {
    return { left: 0, top: 0, width: container.width, height: container.height };
  }
  const scale = Math.min(container.width / video.width, container.height / video.height);
  const width = video.width * scale;
  const height = video.height * scale;
  return {
    left: (container.width - width) / 2,
    top: (container.height - height) / 2,
    width,
    height,
  };
}
