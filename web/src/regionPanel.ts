import type { Route } from "./router"

export type RouteName = Route["name"]

// The region summary sheet replaces the landing/explore sheet while a
// public region is zoomed, unless the user is drawing a field.
export const showRegionPanel = (route: RouteName, regionZoomed: boolean, drawing: boolean) =>
  regionZoomed && !drawing && (route === "landing" || route === "explore")
