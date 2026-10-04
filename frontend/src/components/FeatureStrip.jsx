const FEATURES = [
  {
    number: "01",
    color: "violet",
    title: "Find the story",
    description: "AI-selected hooks & moments",
  },
  {
    number: "02",
    color: "blue",
    title: "Keep them in frame",
    description: "Face-tracked vertical crop",
  },
  {
    number: "03",
    color: "green",
    title: "Ready to post",
    description: "Download your finished clips",
  },
];

function FeatureStrip() {
  return (
    <section className="feature-strip" aria-label="Pipeline features">
      {FEATURES.map((feature) => (
        <div className="feature" key={feature.number}>
          <span className={`feature-icon feature-icon-${feature.color}`}>{feature.number}</span>
          <span>
            <strong>{feature.title}</strong>
            <small>{feature.description}</small>
          </span>
        </div>
      ))}
    </section>
  );
}

export default FeatureStrip;
