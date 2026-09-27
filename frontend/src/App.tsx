import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { ListingPage } from "./pages/ListingPage";
import { ModerationPage } from "./pages/ModerationPage";
import { MyListingsPage } from "./pages/MyListingsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PublishPage } from "./pages/PublishPage";
import { RegulationsPage } from "./pages/RegulationsPage";
import { SearchPage } from "./pages/SearchPage";

/** A new page starts at the top, as on a site served page by page, and a link to a section scrolls to it. */
function ScrollOnNavigation() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    const section = hash ? document.getElementById(hash.slice(1)) : null;
    if (section) section.scrollIntoView({ behavior: "smooth" });
    else window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

export function App() {
  return (
    <>
      <ScrollOnNavigation />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="alquiler" element={<SearchPage />} />
          <Route path="alquiler/:id" element={<ListingPage />} />
          <Route path="normativa" element={<RegulationsPage />} />
          {/* One route for a new listing and for a draft: saving a new one gives it an address without a remount. */}
          <Route path="publicar/:id?" element={<PublishPage />} />
          <Route path="mis-anuncios" element={<MyListingsPage />} />
          <Route path="moderacion" element={<ModerationPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </>
  );
}
