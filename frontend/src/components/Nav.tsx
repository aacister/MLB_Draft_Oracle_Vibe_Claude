import { NavLink } from "react-router-dom";
import { Trophy, Activity, LineChart, Home as HomeIcon } from "lucide-react";

const items = [
  { to: "/", label: "Home", icon: HomeIcon },
  { to: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { to: "/adp-trends", label: "ADP Trends", icon: LineChart },
];

export function Nav() {
  return (
    <nav className="bg-[#032147] text-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
        <div className="flex items-center gap-2">
          <Activity className="text-[#ecad0a]" size={24} />
          <span className="text-lg font-semibold">MLB Draft Oracle</span>
        </div>
        <div className="ml-8 flex gap-6">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-1.5 text-sm transition ${
                  isActive ? "text-[#ecad0a]" : "text-white hover:text-[#209dd7]"
                }`
              }
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
