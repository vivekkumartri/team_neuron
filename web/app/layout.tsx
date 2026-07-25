import "./globals.css";

export const metadata = {
  title: "Story Engine",
  description: "AI-assisted branching story generation.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
