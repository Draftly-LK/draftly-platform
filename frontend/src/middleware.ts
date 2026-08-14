import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";
import { isAuthBypassEnabled, warnIfBypassSetInProduction } from "@/lib/auth/bypass";
import { isClerkConfigured } from "@/lib/auth/clerk";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/clerk-not-configured(.*)",
]);

const clerkAuthMiddleware = clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  warnIfBypassSetInProduction();

  // AUTH_BYPASS=true skips auth for local development.
  // isAuthBypassEnabled() already returns false in NODE_ENV=production.
  if (isAuthBypassEnabled()) {
    return NextResponse.next();
  }

  // Fail closed: if Clerk keys are missing, redirect every non-static request
  // to an error page rather than serving the app without authentication.
  if (!isClerkConfigured()) {
    const url = request.nextUrl.clone();
    if (url.pathname !== "/clerk-not-configured") {
      url.pathname = "/clerk-not-configured";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  return clerkAuthMiddleware(request, event);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
