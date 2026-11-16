import { DESKTOP_APP_URL } from "../config";
import { Card } from "./ui";

/** Shown on the static web demo in place of pages that need the AI server. */
export default function DesktopOnly({ title }: { title: string }) {
  return (
    <>
      <div className="page-head">
        <div><h1>{title}</h1></div>
      </div>
      <Card title="Unavailable">
        <p>You can access it by downloading the desktop app.</p>
        <a className="btn primary" href={DESKTOP_APP_URL} target="_blank" rel="noreferrer">Download the desktop app</a>
      </Card>
    </>
  );
}
