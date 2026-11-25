"""Instrument the pinned native Match, not the clock-only unit test."""
import pathlib
import sys

HEADER = r'''
// Tribun Manager modification: opt-in native match trace, Apache-2.0 upstream.
#include <cstdlib>
#include <locale>
#include <iomanip>

namespace {
void TribunTrace(Match& match, bool done) {
  const char* path = std::getenv("TRIBUN_LEAGUE_SOCCER_TRACE");
  if (!path || !*path) return;
  static std::ofstream output(path, std::ios::out | std::ios::trunc);
  static bool started = false;
  static bool finished = false;
  static unsigned long last = 0;
  if (!output || finished) return;
  const auto now = match.GetActualTime_ms();
  if (started && !done && now < last + 100) return;
  started = true;
  last = now;
  finished = done;
  output.imbue(std::locale::classic());
  output << std::setprecision(9);
  const auto vec = [&](const Vector3& v) {
    output << '[' << v.coords[0] << ',' << v.coords[1] << ',' << v.coords[2] << ']';
  };
  output << "{\"schema\":1,\"engine\":\"league-soccer\",\"elapsedMs\":" << now
         << ",\"matchMs\":" << match.GetMatchTime_ms()
         << ",\"done\":" << (done ? "true" : "false")
         << ",\"score\":[" << match.GetScore(0) << ',' << match.GetScore(1)
         << "],\"ball\":";
  vec(match.GetBall()->Predict(0));
  output << ",\"ballVelocity\":";
  vec(match.GetBall()->GetMovement());
  output << ",\"players\":[";
  bool first = true;
  for (int team = 0; team < 2; ++team) {
    std::vector<Player*> players;
    match.GetActiveTeamPlayers(team, players);
    for (auto* player : players) {
      if (!first) output << ',';
      first = false;
      output << "{\"id\":" << player->GetID() << ",\"team\":" << team << ",\"position\":";
      vec(player->GetPosition());
      output << ",\"velocity\":";
      vec(player->GetMovement());
      output << ",\"direction\":";
      vec(player->GetDirectionVec());
      output << '}';
    }
  }
  output << "]}" << std::endl;
}
}
'''

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected upstream layout: {old!r}")
    return text.replace(old, new, 1)

def main():
    path = pathlib.Path(sys.argv[1]) / "src/onthepitch/match.cpp"
    text = path.read_text(encoding="utf-8")
    if "void TribunTrace(" in text:
        return
    anchor = "const unsigned int replaySize_ms = 10000;"
    text = replace_once(text, anchor, HEADER + "\n" + anchor)
    anchor = "  // Tell the game page once; the full-time screen used to be re-created"
    text = replace_once(text, anchor, "  TribunTrace(*this, gameOver);\n\n" + anchor)
    path.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
