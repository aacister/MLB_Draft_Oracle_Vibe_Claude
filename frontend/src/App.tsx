import { Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { AdpTrends } from "./pages/AdpTrends";
import { DraftRoom } from "./pages/DraftRoom";
import { Grade } from "./pages/Grade";
import { Home } from "./pages/Home";
import { Leaderboard } from "./pages/Leaderboard";

export default function App() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/drafts/:draftId" element={<DraftRoom />} />
          <Route path="/drafts/:draftId/grade" element={<Grade />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/adp-trends" element={<AdpTrends />} />
        </Routes>
      </main>
    </div>
  );
}
