import { BrainCircuit, Gauge, Inbox, ScrollText } from "lucide-react";
import { useSession } from "@/auth/session";
import { Card, PageHeader } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Short, role-first help: three steps per role, nothing more. */
const GUIDES = [
  {
    role: "gestionnaire",
    icon: Inbox,
    title: "Gestionnaire sinistres",
    steps: [
      "Cliquez « Traiter le dossier suivant » : le plus urgent s'ouvre et vous est réservé 15 min.",
      "Lisez l'e-mail à gauche : les passages surlignés prouvent chaque valeur proposée.",
      "À droite, corrigez ce qui est faux (✕ si la valeur est inventée), puis Ctrl + Entrée.",
    ],
    note: "Groupe témoin : certains dossiers n'ont pas de proposition. C'est voulu, pour mesurer le gain réel.",
  },
  {
    role: "responsable",
    icon: Gauge,
    title: "Responsable d'équipe",
    steps: [
      "Pilotage : stock, retards et traités du jour, mis à jour en continu.",
      "« Valeur de l'IA, mesurée » compare les deux groupes : même équipe, avec et sans IA.",
      "Mode tempête : déclenchez un événement climatique et suivez la vague en direct (stock, retards, délai de résorption).",
    ],
    note: "Indicateurs d'équipe uniquement : l'outil ne classe pas les personnes.",
  },
  {
    role: "auditeur",
    icon: ScrollText,
    title: "Auditeur conformité",
    steps: [
      "Le journal liste chaque action : qui (humain, IA, système), quoi, quand, sur quel dossier.",
      "« Vérifier l'intégrité » recalcule toutes les empreintes : une modification se voit.",
      "« Rapport de supervision » : une page scellée qui prouve qui a décidé quoi, avec quelle IA — à imprimer en PDF.",
    ],
    note: "La base de données refuse toute modification ou suppression du journal.",
  },
  {
    role: "equipe_ia",
    icon: BrainCircuit,
    title: "Équipe IA",
    steps: [
      "Tour de contrôle : branchez une IA externe (clé d'API), elle tourne en fantôme sur les mêmes dossiers.",
      "Comparez sur « accord sans biais » (groupe témoin), puis promouvez la meilleure en champion.",
      "Une alerte de dérive apparaît si les gestionnaires se mettent à corriger davantage.",
    ],
    note: "Budget journalier dépassé ou modèle en panne : repli automatique sur les règles.",
  },
];

export function HelpPage() {
  const me = useSession()?.user.role;
  return (
    <div>
      <PageHeader title="Aide" />
      <div className="grid gap-4 md:grid-cols-2">
        {[...GUIDES].sort((a, b) => Number(b.role === me) - Number(a.role === me)).map((g) => {
          const Icon = g.icon;
          return (
            <Card key={g.role} className={cn("p-5", g.role === me && "border-accent ring-1 ring-accent/20")}>
              <div className="flex items-center gap-2">
                <Icon size={18} className="text-accent" aria-hidden />
                <h2 className="font-semibold">{g.title}</h2>
              </div>
              <ol className="mt-3 list-inside list-decimal space-y-1.5 text-sm">
                {g.steps.map((s) => <li key={s}>{s}</li>)}
              </ol>
              <p className="mt-3 text-xs text-muted">{g.note}</p>
            </Card>
          );
        })}
      </div>
      <Card className="mt-4 p-5 text-sm text-muted">
        <strong className="text-ink">Limites du prototype.</strong> Données entièrement fictives,
        petit pilote, adresses postales non masquées. L'outil ne prend aucune décision de garantie,
        de refus ou de fraude.
      </Card>
    </div>
  );
}
