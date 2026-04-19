export interface UIComponent {
  type: string;
  props: Record<string, any>;
  children?: string | UIComponent[];
  styles?: Record<string, string>;
}

export class GenerativeUIService {
  private baseUrl: string;

  constructor(baseUrl: string = '/api/ai') {
    this.baseUrl = baseUrl;
  }

  async generateComponent(description: string, componentType: string): Promise<UIComponent> {
    try {
      const response = await fetch(`${this.baseUrl}/generate-ui`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          description,
          componentType,
          context: 'ekioba-marketplace'
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to generate UI: ${response.statusText}`);
      }

      const data = await response.json();
      return data.component;
    } catch (error) {
      console.error('Error generating UI component:', error);
      // Fallback to basic component
      return {
        type: componentType,
        props: {
          className: 'generated-component bg-blue-500 text-white px-4 py-2 rounded',
          children: description,
        },
      };
    }
  }

  async generateLayout(description: string): Promise<UIComponent[]> {
    try {
      const response = await fetch(`${this.baseUrl}/generate-layout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          description,
          context: 'ekioba-marketplace'
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to generate layout: ${response.statusText}`);
      }

      const data = await response.json();
      return data.layout;
    } catch (error) {
      console.error('Error generating layout:', error);
      return [];
    }
  }
}

export const generativeUIService = new GenerativeUIService();