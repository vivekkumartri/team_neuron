import "./globals.css";

export const metadata = {
  title: "Brahma",
  description: "AI-assisted branching story generation.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
