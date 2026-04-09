import type { Metadata, Viewport } from 'next'
import Script from 'next/script'
import './globals.css'

export const metadata: Metadata = {
  title: 'InsightAI — AI-Powered Survey & Insight Engine',
  description: 'Turn conversations into clarity with AI-powered surveys',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#030712',
}

const isDev = process.env.NODE_ENV === 'development'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {isDev ? (
          <Script
            id="dev-metamask-noise-filter"
            strategy="beforeInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                (function () {
                  if (typeof window === 'undefined') return;

                  function isMetaMaskNoise(value) {
                    var text = String(value || '');
                    return text.indexOf('MetaMask') !== -1 ||
                           text.indexOf('Failed to connect to MetaMask') !== -1 ||
                           text.indexOf('chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn') !== -1;
                  }

                  window.addEventListener('unhandledrejection', function (event) {
                    var reason = event && event.reason;
                    var message = reason && reason.message ? reason.message : reason;
                    if (isMetaMaskNoise(reason) || isMetaMaskNoise(message)) {
                      event.preventDefault();
                    }
                  }, true);

                  window.addEventListener('error', function (event) {
                    if (isMetaMaskNoise(event && event.message) || isMetaMaskNoise(event && event.filename)) {
                      event.preventDefault();
                    }
                  }, true);
                })();
              `,
            }}
          />
        ) : null}
        {children}
      </body>
    </html>
  )
}
