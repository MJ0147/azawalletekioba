export class GenerativeUIService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_IYOBO_API_URL!;
  }

  async generateComponent(description: string, componentType: string) {
    const response = await fetch(`${this.baseUrl}/generate-ui`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description,
        componentType,
        context: "ekioba-marketplace"
      })
    });

    return (await response.json()).component;
  }

  async generateLayout(description: string) {
    const response = await fetch(`${this.baseUrl}/generate-layout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description,
        context: "ekioba-marketplace"
      })
    });

    return (await response.json()).layout;
  }
}
