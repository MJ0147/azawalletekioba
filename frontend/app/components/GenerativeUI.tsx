"use client";

import { useCopilotAction } from "@copilotkit/react-core";
import { useState } from "react";
import { generativeUIService, UIComponent } from "../services/generativeUI";

export default function GenerativeUI() {
  const [generatedComponents, setGeneratedComponents] = useState<UIComponent[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  useCopilotAction({
    name: "generateUI",
    description: "Generate UI components based on user description using AI",
    parameters: [
      {
        name: "description",
        type: "string",
        description: "Description of the UI component to generate",
        required: true,
      },
      {
        name: "componentType",
        type: "string",
        description: "Type of component (button, card, form, input, etc.)",
        required: true,
      },
    ],
    handler: async ({ description, componentType }) => {
      setIsGenerating(true);
      try {
        const newComponent = await generativeUIService.generateComponent(description, componentType);
        setGeneratedComponents(prev => [...prev, newComponent]);
      } catch (error) {
        console.error('Failed to generate component:', error);
        // Fallback component
        const fallbackComponent: UIComponent = {
          type: componentType,
          props: {
            className: 'generated-component bg-red-100 border border-red-300 text-red-700 px-4 py-2 rounded',
            children: `Generated ${componentType}: ${description}`,
          },
        };
        setGeneratedComponents(prev => [...prev, fallbackComponent]);
      } finally {
        setIsGenerating(false);
      }
    },
  });

  useCopilotAction({
    name: "generateLayout",
    description: "Generate a complete UI layout based on description",
    parameters: [
      {
        name: "description",
        type: "string",
        description: "Description of the layout to generate",
        required: true,
      },
    ],
    handler: async ({ description }) => {
      setIsGenerating(true);
      try {
        const layout = await generativeUIService.generateLayout(description);
        setGeneratedComponents(prev => [...prev, ...layout]);
      } catch (error) {
        console.error('Failed to generate layout:', error);
      } finally {
        setIsGenerating(false);
      }
    },
  });

  const renderComponent = (component: UIComponent): JSX.Element => {
    const { type, props, children, styles } = component;

    const componentProps = {
      ...props,
      style: styles,
    };

    switch (type) {
      case "button":
        return <button {...componentProps}>{children}</button>;
      case "input":
        return <input {...componentProps} />;
      case "textarea":
        return <textarea {...componentProps}>{children}</textarea>;
      case "card":
        return (
          <div {...componentProps}>
            {typeof children === "string" ? children : children?.map(renderComponent)}
          </div>
        );
      case "form":
        return (
          <form {...componentProps}>
            {typeof children === "string" ? children : children?.map(renderComponent)}
          </form>
        );
      case "div":
      case "section":
        return (
          <div {...componentProps}>
            {typeof children === "string" ? children : children?.map(renderComponent)}
          </div>
        );
      default:
        return <div {...componentProps}>{children}</div>;
    }
  };

  return (
    <div className="generative-ui-container border rounded-lg p-6 bg-white dark:bg-gray-800 shadow-sm">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
        🤖 Generative UI with Copilot
      </h3>

      {isGenerating && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
          <div className="flex items-center">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
            Generating component...
          </div>
        </div>
      )}

      <div className="generated-components space-y-4">
        {generatedComponents.map((component, index) => (
          <div key={index} className="border rounded p-4 bg-gray-50 dark:bg-gray-700">
            <div className="text-xs text-gray-500 mb-2">Component {index + 1}: {component.type}</div>
            {renderComponent(component)}
          </div>
        ))}
      </div>

      {generatedComponents.length === 0 && !isGenerating && (
        <div className="text-center py-8">
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Ask Copilot to generate UI components!
          </p>
          <div className="text-sm text-gray-400 space-y-1">
            <p>Try: "Create a blue submit button"</p>
            <p>Try: "Generate a contact form with name and email fields"</p>
            <p>Try: "Create a product card with image, title, and price"</p>
          </div>
        </div>
      )}

      {generatedComponents.length > 0 && (
        <button
          onClick={() => setGeneratedComponents([])}
          className="mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
        >
          Clear All Components
        </button>
      )}
    </div>
  );
}