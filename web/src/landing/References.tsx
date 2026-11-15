// The long source list. Linked only from the top menu, because it is a lot of text.

type Link = { label: string; href: string };
type Group = { title: string; note?: string; links: Link[] };

const GROUPS: Group[] = [
  {
    title: "NASA data",
    note: "The pages and files the project actually read. Hazards and risks told us what to watch. The evidence reports are where a kept number has a page. Inspiration4 is real crew lab context, kept apart from the demo.",
    links: [
      { label: "NASA Open Science Data Repository (OSDR)", href: "https://osdr.nasa.gov/" },
      { label: "NASA OSDR Public API", href: "https://www.nasa.gov/osdr-api/" },
      { label: "OSD-569: SpaceX Inspiration4 Complete Blood Count", href: "https://osdr.nasa.gov/bio/repo/data/studies/OSD-569" },
      { label: "OSD-575: SpaceX Inspiration4 Metabolic & Cardiovascular Panels", href: "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" },
      { label: "NASA HRP – 5 Hazards of Human Spaceflight", href: "https://www.nasa.gov/hrp/hazards/" },
      { label: "NASA HRP – Risks of Human Spaceflight", href: "https://www.nasa.gov/hrp/risks/" },
      { label: "NASA HRP – Ongoing HRP Research in Space", href: "https://www.nasa.gov/hrp/ongoing-hrp-research/" },
      { label: "NASA Human Research Roadmap", href: "https://humanresearchroadmap.nasa.gov/" },
      { label: "NASA Evidence Report – Risk of Bone Fracture", href: "https://humanresearchroadmap.nasa.gov/Evidence/reports/Fracture.pdf" },
      { label: "NASA Evidence Report – Cardiovascular Risk", href: "https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf" },
      { label: "NASA Evidence Report – Degenerative Tissue Risk", href: "https://humanresearchroadmap.nasa.gov/evidence/reports/Degen.pdf" },
      { label: "NASA – Human Adaptation to Spaceflight: Role of Food and Nutrition", href: "https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf" },
      { label: "NASA-STD-3001 Technical Brief – Bone Loss", href: "https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-030-bone-loss.pdf" },
      { label: "NASA-STD-3001 Technical Brief – Venous Thrombosis", href: "https://www.nasa.gov/wp-content/uploads/2026/01/ochmo-mtb-007-venous-thrombosis-in-spaceflight.pdf" },
      { label: "NASA HRP Risk Approach Plans", href: "https://www.nasa.gov/wp-content/uploads/2026/06/hrp-rap-for-web-62026.pdf" },
      { label: "NASA HRP Hazard – Gravity Fields", href: "https://www.nasa.gov/hrp/hazard-gravity-fields/" },
      { label: "NASA HRP Hazard – Isolation and Confinement", href: "https://www.nasa.gov/hrp/hazard-isolation-and-confinement/" },
      { label: "NASA HRP Hazard – Space Radiation", href: "https://www.nasa.gov/hrp/hazard-space-radiation/" },
      { label: "NASA HRP Hazard – Hostile/Closed Environments", href: "https://www.nasa.gov/hrp/hazard-hostile-closed-environments/" },
      { label: "NASA HRP Hazard – Distance From Earth", href: "https://www.nasa.gov/hrp/hazard-distance-from-earth/" },
      { label: "NASA Risk – Inadequate Sleep and Irregular Schedules", href: "https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/" },
      { label: "NASA Risk – Cardiovascular Adaptations", href: "https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/" },
      { label: "NASA Risk – Behavioral Conditions and Psychiatric Disorders", href: "https://www.nasa.gov/reference/risk-of-behavioral-conditions-and-psychiatric-disorders/" },
      { label: "NASA Risk – Spaceflight-Induced Bone Changes", href: "https://www.nasa.gov/reference/risk-of-spaceflight-induced-bone-changes/" },
      { label: "NASA Risk – Inadequate Food and Nutrition", href: "https://www.nasa.gov/reference/risk-of-inadequate-food-and-nutrition/" },
      { label: "NASA Risk – Reduced Cardiorespiratory and Musculoskeletal Fitness", href: "https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/" },
      { label: "NASA Standard Measures Study", href: "https://www.nasa.gov/reference/standard-measures/" },
      { label: "NASA CIPHER Study", href: "https://www.nasa.gov/reference/cipher/" },
      { label: "NASA-TLX Workload Index (NASA Ames)", href: "https://humansystems.arc.nasa.gov/groups/tlx/" },
    ],
  },
  {
    title: "The other HRP risk pages",
    note: "Seventeen risks in all. Six are in the list above because the demo watches something close to them. These eleven are the rest. The assistant may quote them. They are not wearable time series.",
    links: [
      { label: "Risk of Altered Immune System Responses", href: "https://www.nasa.gov/reference/risk-of-altered-immune-system-responses/" },
      { label: "Risk of Altered Sensorimotor and Vestibular Function", href: "https://www.nasa.gov/reference/risk-of-altered-sensorimotor-and-vestibular-function/" },
      { label: "Risk of Decompression Sickness", href: "https://www.nasa.gov/reference/risk-of-decompression-sickness/" },
      { label: "Risk of Host-Microorganism Interactions", href: "https://www.nasa.gov/reference/risk-of-host-microorganism-interactions/" },
      { label: "Risk of Hypoxia", href: "https://www.nasa.gov/reference/risk-of-hypoxia/" },
      { label: "Risk of Inadequate Systems Operations Support", href: "https://www.nasa.gov/reference/risk-of-inadequate-systems-operations-support/" },
      { label: "Risk of Inadequate Teamwork", href: "https://www.nasa.gov/reference/risk-of-inadequate-teamwork/" },
      { label: "Risk of Injury and Compromised Performance from Spacewalks", href: "https://www.nasa.gov/reference/risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva/" },
      { label: "Risk of Injury from Dynamic Loads", href: "https://www.nasa.gov/reference/risk-of-injury-from-dynamic-loads/" },
      { label: "Risk of Radiation-Induced Cancers", href: "https://www.nasa.gov/reference/risk-of-radiation-induced-cancers/" },
      { label: "Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)", href: "https://www.nasa.gov/reference/risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/" },
    ],
  },
  {
    title: "The other study pages",
    note: "Standard Measures and CIPHER are listed with the NASA data above. These are the other study pages from the challenge resources. They describe the measurements NASA wants. They do not publish the crew time series.",
    links: [
      { label: "ARCHeR", href: "https://www.nasa.gov/reference/archer/" },
      { label: "Artemis II Standard Measures", href: "https://www.nasa.gov/reference/artemis-ii-standard-measures/" },
      { label: "B-Complex", href: "https://www.nasa.gov/reference/b-complex/" },
      { label: "Brain Fluid Pressure", href: "https://www.nasa.gov/reference/brain-fluid-pressure/" },
      { label: "Immune Biomarkers", href: "https://www.nasa.gov/reference/immune-biomarkers/" },
      { label: "Omics Archive", href: "https://www.nasa.gov/reference/omics-archive/" },
      { label: "Simulating Manual Piloting for Moon Landings", href: "https://www.nasa.gov/reference/simulating-manual-piloting-for-moon-landings/" },
      { label: "Spacecraft Occupant Protection", href: "https://www.nasa.gov/reference/spacecraft-occupant-protection/" },
      { label: "Spinal Fluid Biomarkers", href: "https://www.nasa.gov/reference/spinal-fluid-biomarkers/" },
      { label: "Tempus Pro", href: "https://www.nasa.gov/reference/tempus-pro/" },
      { label: "Thigh Cuff", href: "https://www.nasa.gov/reference/thigh-cuff/" },
      { label: "Venous Haemostasis", href: "https://www.nasa.gov/reference/venous-haemostasis/" },
      { label: "Zero T2", href: "https://www.nasa.gov/reference/zero-t2/" },
    ],
  },
  {
    title: "HRP element pages",
    note: "Short pages on the groups inside the Human Research Program.",
    links: [
      { label: "Human Factors and Behavioral Performance", href: "https://www.nasa.gov/hrp/human-factors-and-behavioral-performance/" },
      { label: "Human Health Countermeasures", href: "https://www.nasa.gov/hrp/human-health-countermeasures/" },
      { label: "Space Radiation", href: "https://www.nasa.gov/hrp/radiation/" },
    ],
  },
  {
    title: "Space agencies, papers, and datasets",
    note: "Partner pages, the Inspiration4 paper, and the Earth studies the models were checked on. Earth studies are not astronaut data.",
    links: [
      { label: "CSA – Monitoring Radiation for Astronaut Health", href: "https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp" },
      { label: "CSA – Why Do We Conduct Science Experiments in Space?", href: "https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp" },
      { label: "Inspiration4 paper (Overbey et al., Nature 2024)", href: "https://doi.org/10.1038/s41586-024-07639-y" },
      { label: "PMData Sports Logging Dataset (Simula)", href: "https://datasets.simula.no/pmdata" },
      { label: "PMData on OSF", href: "https://osf.io/vx4bk" },
      { label: "Stanford COVID-19 Smartwatch Data (Mishra et al., 2020)", href: "https://doi.org/10.1038/s41551-020-00640-6" },
      { label: "CGMacros Dataset (PhysioNet)", href: "https://physionet.org/content/cgmacros/1.0.0/" },
      { label: "MMASH Dataset (PhysioNet)", href: "https://physionet.org/content/mmash/1.0.0/" },
      { label: "CVES Cerebral Vasoregulation Dataset (PhysioNet)", href: "https://physionet.org/content/cves/1.0.0/" },
      { label: "Europe PMC REST API (CC BY open-access abstracts)", href: "https://europepmc.org/RestfulWebService" },
    ],
  },
  {
    title: "Models and libraries",
    note: "What the language-model work and the health models were built with.",
    links: [
      { label: "Qwen2.5 7B Instruct", href: "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct" },
      { label: "Qwen2.5 14B Instruct", href: "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct" },
      { label: "Qwen2.5 32B Instruct", href: "https://huggingface.co/Qwen/Qwen2.5-32B-Instruct" },
      { label: "Ollama", href: "https://ollama.com" },
      { label: "Hugging Face Transformers", href: "https://github.com/huggingface/transformers" },
      { label: "Hugging Face PEFT (LoRA/QLoRA)", href: "https://github.com/huggingface/peft" },
      { label: "Hugging Face TRL", href: "https://github.com/huggingface/trl" },
      { label: "bitsandbytes", href: "https://github.com/bitsandbytes-foundation/bitsandbytes" },
      { label: "PyTorch", href: "https://pytorch.org" },
      { label: "scikit-learn", href: "https://scikit-learn.org" },
      { label: "pandas", href: "https://pandas.pydata.org" },
      { label: "NumPy", href: "https://numpy.org" },
      { label: "pypdf", href: "https://github.com/py-pdf/pypdf" },
    ],
  },
  {
    title: "The app, phones, and hosting",
    links: [
      { label: "FastAPI", href: "https://fastapi.tiangolo.com" },
      { label: "SQLAlchemy", href: "https://www.sqlalchemy.org" },
      { label: "PostgreSQL", href: "https://www.postgresql.org" },
      { label: "Eclipse Mosquitto (MQTT broker)", href: "https://mosquitto.org" },
      { label: "Eclipse Paho MQTT Python", href: "https://github.com/eclipse-paho/paho.mqtt.python" },
      { label: "MediaPipe Tasks Vision (pose tracking)", href: "https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker" },
      { label: "React", href: "https://react.dev" },
      { label: "Vite", href: "https://vite.dev" },
      { label: "Recharts", href: "https://recharts.org" },
      { label: "React Router", href: "https://reactrouter.com" },
      { label: "Fontsource (IBM Plex, Kalam, Patrick Hand fonts)", href: "https://fontsource.org" },
      { label: "Apple HealthKit", href: "https://developer.apple.com/documentation/healthkit" },
      { label: "Android Health Connect", href: "https://developer.android.com/health-and-fitness/guides/health-connect" },
      { label: "Docker", href: "https://www.docker.com" },
      { label: "Caddy", href: "https://caddyserver.com" },
      { label: "DigitalOcean (GPU droplet hosting)", href: "https://www.digitalocean.com" },
    ],
  },
];

export default function References() {
  return (
    <section className="sk-section sk-refpage" id="references">
      <h2><span className="sk-hl">references</span></h2>
      <p className="sk-lead">every page, dataset and tool this project used. open one if you want the original. none of these links is a claim that HEALTH-01 has been tried on astronauts.</p>
      <div className="sk-refgrid">
        {GROUPS.map((group) => (
          <article key={group.title} className="sk-paper">
            <h3>{group.title}</h3>
            {group.note && <p>{group.note}</p>}
            <ul className="sk-reflist">
              {group.links.map((link) => (
                <li key={link.href}><a href={link.href} target="_blank" rel="noreferrer">{link.label}</a></li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
