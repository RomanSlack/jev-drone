import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Source_Serif_4, IBM_Plex_Mono } from "next/font/google";
import { SITE_URL, REPO_URL, TITLE, HEADLINE, DESCRIPTION } from "@/lib";
import "./globals.css";

const display = IBM_Plex_Sans({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-display", display: "swap" });
const body = Source_Serif_4({ subsets: ["latin"], style: ["normal", "italic"], variable: "--font-body", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-mono", display: "swap" });

const OG_ALT = "jev-drone: recorded top-down flight path through slalom, beam, turnstiles, gate and cluster. 77.5 m with Jev against 17.7 m for the baseline.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  keywords: [
    "autonomous drone",
    "MuJoCo drone simulation",
    "quadrotor obstacle avoidance",
    "camera-only navigation",
    "LLM in the control loop",
    "judgment model",
    "TypeSafe Jev",
    "Skydio X2 MuJoCo Menagerie",
    "geometric controller",
    "quaternion attitude control",
    "robotics ablation study",
  ],
  authors: [{ name: "Roman Slack", url: "https://github.com/RomanSlack" }],
  creator: "Roman Slack",
  alternates: { canonical: "/" },
  openGraph: {
    type: "article",
    url: "/",
    siteName: "jev-drone",
    locale: "en_US",
    title: HEADLINE,
    description: DESCRIPTION,
    publishedTime: "2026-09-16",
    modifiedTime: "2026-09-21",
    authors: ["Roman Slack"],
    tags: ["MuJoCo", "autonomous drone", "robotics", "judgment model", "TypeSafe Jev"],
    images: [{ url: "/og.png", width: 1200, height: 630, type: "image/png", alt: OG_ALT }],
  },
  twitter: { card: "summary_large_image", title: HEADLINE, description: DESCRIPTION, images: [{ url: "/og.png", alt: OG_ALT }] },
  category: "technology",
  robots: { index: true, follow: true, googleBot: { "max-image-preview": "large", "max-video-preview": -1 } },
};

export const viewport: Viewport = { themeColor: "#ffffff", width: "device-width", initialScale: 1 };

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "TechArticle",
      "@id": `${SITE_URL}/#article`,
      headline: HEADLINE,
      description: DESCRIPTION,
      image: { "@type": "ImageObject", url: `${SITE_URL}/og.png`, width: 1200, height: 630 },
      datePublished: "2026-09-16",
      dateModified: "2026-09-21",
      author: { "@type": "Person", name: "Roman Slack", url: "https://github.com/RomanSlack" },
      publisher: { "@type": "Person", name: "Roman Slack", url: "https://github.com/RomanSlack" },
      inLanguage: "en",
      keywords: "MuJoCo, autonomous drone, quadrotor, obstacle avoidance, judgment model, TypeSafe Jev, control loop",
      mainEntityOfPage: SITE_URL,
      about: ["Autonomous drones", "MuJoCo", "Robot control", "Language models in control loops"],
      isBasedOn: REPO_URL,
    },
    { "@type": "WebSite", "@id": `${SITE_URL}/#website`, url: SITE_URL, name: "jev-drone", description: DESCRIPTION, inLanguage: "en" },
    {
      "@type": "SoftwareSourceCode",
      "@id": `${SITE_URL}/#code`,
      name: "jev-drone",
      description: DESCRIPTION,
      codeRepository: REPO_URL,
      programmingLanguage: "Python",
      runtimePlatform: "MuJoCo 3",
      license: "https://opensource.org/licenses/MIT",
      author: { "@type": "Person", name: "Roman Slack" },
    },
    {
      "@type": "VideoObject",
      name: "Camera-only drone clears a five-station MuJoCo obstacle course",
      description: "Full 47 second run: slalom, low beam, turnstiles, sliding gate and pillar cluster, with the live Jev judgment panel.",
      thumbnailUrl: `${SITE_URL}/figures/course-poster.jpg`,
      contentUrl: `${SITE_URL}/figures/course-run.mp4`,
      uploadDate: "2026-09-16",
      duration: "PT48S",
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <a className="skip" href="#main">Skip to content</a>
        {children}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      </body>
    </html>
  );
}
