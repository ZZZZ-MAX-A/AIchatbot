type ErrorStateProps = {
  title: string;
  description: string;
  details?: string;
};

export function ErrorState({ title, description, details }: ErrorStateProps) {
  return (
    <section className="error-state" role="status">
      <h2>{title}</h2>
      <p>{description}</p>
      {details ? <pre>{details}</pre> : null}
    </section>
  );
}
