import { Html, Head, Main, NextScript } from "next/document";

import { THEME_BOOT_SCRIPT } from "@/lib/theme";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </Head>
      <body>
        {/* Must run synchronously before Main renders, or the page paints
            in light mode for an instant even when dark was stored --
            a useEffect-based approach runs after that first paint, which is
            exactly the flash this exists to prevent. No user input reaches
            this script (THEME_BOOT_SCRIPT is a fixed constant), so inlining
            it is safe. */}
        {/* eslint-disable-next-line react/no-danger */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
