/**
 * In-product help: for every screen, what it is for, when to use it, how, and why each
 * element exists. Shown in the "?" drawer and, element by element, in <InfoTip>.
 * One source of truth so the guide, the tooltips and the screens never disagree.
 */

export interface HelpElement {
  name: string;
  what: string;
  why: string;
}

export interface ScreenHelp {
  title: string;
  purpose: string;
  when: string;
  steps: string[];
  elements: HelpElement[];
  shortcuts?: [string, string][];
}

export const SCREENS: Record<string, ScreenHelp> = {
  queue: {
    title: "Corbeille",
    purpose: "La liste des e-mails sinistres à traiter, les plus urgents en premier.",
    when: "Au début de la journée, et chaque fois que vous terminez un dossier.",
    steps: [
      "Cliquez « Traiter le dossier suivant » : l'outil ouvre le plus urgent qui est libre.",
      "Si besoin, filtrez par priorité ou par événement climatique.",
      "Un dossier déjà ouvert par un collègue affiche un cadenas : il est réservé 15 min.",
    ],
    elements: [
      { name: "Priorité", what: "Urgente, haute, normale ou basse, calculée par des règles lisibles (relogement, fuite active, personne vulnérable, échéance…).",
        why: "Pour traiter d'abord les personnes qui en ont le plus besoin, et pouvoir expliquer pourquoi." },
      { name: "Délai", what: "Le temps restant avant le délai cible (4 h pour une urgence, 24 h haute, 72 h normale).",
        why: "Un retard se voit avant qu'il n'arrive ; le responsable suit les mêmes délais." },
      { name: "« Sans tri »", what: "Dossier du groupe témoin : l'IA ne montre rien, vous traitez à la main.",
        why: "C'est la référence qui permet de mesurer si l'IA fait vraiment gagner du temps." },
      { name: "« À vérifier »", what: "L'IA est peu sûre d'elle, ou le modèle n'a pas répondu (repli sur des règles).",
        why: "Pour regarder ces dossiers avec plus d'attention." },
    ],
    shortcuts: [["Entrée", "Ouvrir le dossier sélectionné"], ["?", "Afficher cette aide"]],
  },
  case: {
    title: "Dossier",
    purpose: "Traiter un e-mail : le lire, vérifier ce que l'IA propose, décider.",
    when: "Chaque fois que vous ouvrez un dossier depuis la corbeille.",
    steps: [
      "Lisez le verdict en haut : « Prêt à valider », ou les points « À vérifier ».",
      "Comparez chaque valeur avec son passage surligné (« voir la source ») ; corrigez ou rejetez ce qui est faux.",
      "Faites les actions de l'onglet « À faire », copiez la réponse si besoin.",
      "Validez (Ctrl + Entrée). Le dossier suivant s'ouvre tout seul.",
    ],
    elements: [
      { name: "Verdict", what: "« Prêt à valider » si tout est justifié par l'e-mail ; « À vérifier » avec la liste des points à regarder.",
        why: "Savoir en 2 secondes si le dossier demande de l'attention, et où regarder." },
      { name: "Contexte du dossier", what: "Quatre onglets autour de l'e-mail : À faire, Contrat, Historique, Réponse. Ils suivent le formulaire.",
        why: "Avoir sous la main ce qu'on irait chercher dans trois autres outils, sans quitter le dossier." },
      { name: "À faire maintenant", what: "Les actions métier recommandées pour ce type d'e-mail (rappeler, missionner un expert, accuser réception…).",
        why: "Pour ne rien oublier, surtout sur les cas urgents. Ce sont des règles de l'équipe, pas l'IA." },
      { name: "Contrat", what: "La formule, les garanties et la franchise du contrat cité, et si le dommage est couvert (registre simulé).",
        why: "Ne pas promettre une prise en charge que le contrat ne prévoit pas." },
      { name: "Confirmer la catégorie", what: "Quand l'IA n'est pas sûre de la catégorie, vous devez la confirmer ou la changer avant de valider.",
        why: "Éviter de valider par réflexe là où l'IA est la plus faible." },
      { name: "Sans source", what: "Aucun passage de l'e-mail ne justifie cette valeur : elle est peut-être devinée ou inventée.",
        why: "C'est la valeur à vérifier en premier ; rejetez-la si l'e-mail ne la contient pas." },
      { name: "Proposition de l'IA", what: "Catégorie, champs clés et résumé, remplis à partir de l'e-mail masqué.",
        why: "Pour éviter la ressaisie. Rien n'est appliqué sans votre validation." },
      { name: "Passages surlignés", what: "La phrase exacte de l'e-mail qui justifie chaque valeur. Cliquez sur un champ pour la retrouver.",
        why: "Vérifier une valeur en un coup d'œil, sans relire tout l'e-mail." },
      { name: "✕ Rejeter", what: "La valeur est fausse ou inventée par l'IA. Un motif est demandé.",
        why: "Les rejets alimentent la mesure de qualité et l'alerte de dérive de l'équipe IA." },
      { name: "Réponse type", what: "Un modèle de réponse au client pour cette catégorie, déjà rempli. Copiez-le dans votre messagerie.",
        why: "Répondre vite, avec le bon ton et les bonnes informations." },
      { name: "Historique", what: "Les autres dossiers du même contrat ou du même expéditeur.",
        why: "Repérer une relance, un doublon ou un client déjà en difficulté." },
      { name: "Détails techniques", what: "Modèle utilisé, coût, et le texte exact envoyé à l'IA (masqué).",
        why: "Transparence : vous pouvez vérifier qu'aucune donnée personnelle n'est partie." },
    ],
    shortcuts: [["Ctrl + Entrée", "Valider le dossier"], ["?", "Afficher cette aide"]],
  },
  pilotage: {
    title: "Pilotage",
    purpose: "La situation de l'équipe en temps réel : stock, retards, gain mesuré de l'IA.",
    when: "En début de journée, en cas de pic (tempête), et avant une réunion d'équipe.",
    steps: [
      "Regardez les 4 chiffres du haut : à traiter, en retard, traités aujourd'hui, temps gagné.",
      "En cas d'événement climatique, déclenchez le mode tempête et suivez le délai de résorption.",
      "Ajustez les hypothèses (volume, coût horaire) pour la projection mensuelle.",
    ],
    elements: [
      { name: "Valeur de l'IA, mesurée", what: "Le même travail, avec et sans IA : temps médian et justesse de la catégorie.",
        why: "Une preuve de gain, pas une promesse. Il faut au moins 5 dossiers par groupe." },
      { name: "Mode tempête", what: "Simule l'arrivée d'une vague d'e-mails après un événement climatique.",
        why: "Vérifier que l'équipe et l'outil tiennent le choc, et estimer le temps de résorption." },
      { name: "Hypothèses", what: "Volume mensuel, minutes de référence, coût horaire : modifiables et tracées.",
        why: "Séparer clairement ce qui est mesuré de ce qui est supposé." },
    ],
  },
  audit: {
    title: "Journal d'audit",
    purpose: "Chaque action, humaine, IA ou système, enregistrée et infalsifiable.",
    when: "Lors d'un contrôle, d'une réclamation ou d'un incident.",
    steps: [
      "Filtrez par acteur, type d'événement ou numéro de dossier.",
      "Cliquez une ligne pour voir le détail et les empreintes.",
      "« Vérifier l'intégrité » recalcule toute la chaîne ; « Rapport de supervision » produit une page scellée.",
    ],
    elements: [
      { name: "Empreinte", what: "Chaque ligne contient l'empreinte de la précédente (SHA-256).",
        why: "Modifier une ligne casserait toutes les suivantes : la fraude se voit." },
      { name: "Registre", what: "Finalité, données, masquage, conservation, destinataires.",
        why: "Répondre aux questions RGPD avec des preuves chiffrées." },
    ],
  },
  report: {
    title: "Rapport de supervision",
    purpose: "Une page qui prouve que les humains ont gardé la main sur une période.",
    when: "Pour un audit, un comité de direction, ou une demande de la conformité.",
    steps: ["Choisissez la période.", "Relisez les 5 sections.", "Imprimez en PDF."],
    elements: [
      { name: "Sceau", what: "L'empreinte du dernier événement du journal au moment du rapport.",
        why: "Toute modification ultérieure du journal sera détectée." },
    ],
  },
  ia: {
    title: "Contrôle des IA",
    purpose: "Comparer toutes les IA sur les mêmes dossiers, détecter une dérive, choisir le champion.",
    when: "Avant de changer de modèle, chaque semaine pour la qualité, et dès qu'une alerte apparaît.",
    steps: [
      "Tour de contrôle : branchez une IA externe, elle tourne en « fantôme » sans être montrée.",
      "Comparez sur « accord sans biais » (dossiers témoins décidés sans IA), puis promouvez la meilleure.",
      "Examen hors ligne : faites passer un test à réponses connues avant toute mise en production.",
    ],
    elements: [
      { name: "Champion / fantôme", what: "Le champion est montré aux gestionnaires ; les fantômes sont notés en silence.",
        why: "Essayer un nouveau fournisseur sans risque, sur du vrai trafic." },
      { name: "Accord sans biais", what: "Accord avec l'humain sur les dossiers du groupe témoin.",
        why: "Un gestionnaire tend à valider ce qu'on lui montre ; le groupe témoin est l'arbitre neutre." },
      { name: "Alertes", what: "Dérive de qualité, champ souvent corrigé, replis, échecs, budget.",
        why: "Une IA se dégrade rarement d'un coup : ce sont les corrections humaines qui préviennent." },
    ],
  },
  aide: {
    title: "Aide",
    purpose: "Trois gestes par rôle, et les limites du prototype.",
    when: "Au premier usage, ou pour présenter l'outil à quelqu'un.",
    steps: ["Lisez la carte de votre rôle.", "Appuyez sur « ? » sur n'importe quel écran pour l'aide détaillée."],
    elements: [],
  },
};

export function screenKey(path: string): keyof typeof SCREENS {
  if (path.startsWith("/dossier")) return "case";
  if (path.startsWith("/journal/rapport")) return "report";
  if (path.startsWith("/journal")) return "audit";
  if (path.startsWith("/pilotage")) return "pilotage";
  if (path.startsWith("/ia")) return "ia";
  if (path.startsWith("/aide")) return "aide";
  return "queue";
}

/** Short explanations for individual elements, used by <InfoTip id="…">. */
export function element(screen: keyof typeof SCREENS, name: string): HelpElement | undefined {
  return SCREENS[screen]?.elements.find((e) => e.name === name);
}
