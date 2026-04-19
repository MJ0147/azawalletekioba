"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { useCopilotAction } from "@copilotkit/react-core";
import { useState } from "react";

interface HeaderFooterGeneratorProps {
  onHeaderGenerated?: (header: string) => void;
  onFooterGenerated?: (footer: string) => void;
}

export default function HeaderFooterGenerator({
  onHeaderGenerated,
  onFooterGenerated
}: HeaderFooterGeneratorProps) {
  const [generatedHeader, setGeneratedHeader] = useState<string>("");
  const [generatedFooter, setGeneratedFooter] = useState<string>("");

  useCopilotAction({
    name: "generateHeader",
    description: "Generate a custom header component with navigation, logo, and styling",
    parameters: [
      {
        name: "brandName",
        type: "string",
        description: "The brand/company name for the header",
        required: true,
      },
      {
        name: "navigationItems",
        type: "string[]",
        description: "Array of navigation menu items",
        required: true,
      },
      {
        name: "style",
        type: "string",
        description: "Styling preference (modern, minimal, corporate, etc.)",
        required: false,
      },
      {
        name: "includeSearch",
        type: "boolean",
        description: "Whether to include a search bar",
        required: false,
      },
      {
        name: "includeUserMenu",
        type: "boolean",
        description: "Whether to include user account menu",
        required: false,
      },
    ],
    handler: async ({ brandName, navigationItems, style, includeSearch, includeUserMenu }) => {
      const headerCode = `
<header class="bg-white shadow-lg border-b">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between items-center h-16">
      <div class="flex items-center">
        <div class="flex-shrink-0">
          <h1 class="text-2xl font-bold text-gray-900">${brandName}</h1>
        </div>
        <nav class="hidden md:ml-6 md:flex md:space-x-8">
          ${navigationItems.map(item => `<a href="#" class="text-gray-900 hover:text-blue-600 px-3 py-2 text-sm font-medium">${item}</a>`).join('')}
        </nav>
      </div>
      <div class="flex items-center space-x-4">
        ${includeSearch ? '<input type="text" placeholder="Search..." class="px-3 py-1 border rounded-md text-sm" />' : ''}
        ${includeUserMenu ? '<button class="text-gray-900 hover:text-blue-600">Account</button>' : ''}
      </div>
    </div>
  </div>
</header>`;

      setGeneratedHeader(headerCode);
      onHeaderGenerated?.(headerCode);
      return `Generated header for ${brandName} with ${navigationItems.length} navigation items`;
    },
  });

  useCopilotAction({
    name: "generateFooter",
    description: "Generate a custom footer component with links, copyright, and social media",
    parameters: [
      {
        name: "brandName",
        type: "string",
        description: "The brand/company name for the footer",
        required: true,
      },
      {
        name: "footerLinks",
        type: "string[]",
        description: "Array of footer link sections",
        required: true,
      },
      {
        name: "socialLinks",
        type: "string[]",
        description: "Array of social media platform names",
        required: false,
      },
      {
        name: "includeNewsletter",
        type: "boolean",
        description: "Whether to include newsletter signup",
        required: false,
      },
    ],
    handler: async ({ brandName, footerLinks, socialLinks, includeNewsletter }) => {
      const footerCode = `
<footer class="bg-gray-900 text-white">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
      <div>
        <h3 class="text-lg font-semibold mb-4">${brandName}</h3>
        <p class="text-gray-400 text-sm">Building the future of digital experiences.</p>
      </div>
      ${footerLinks.map(section => `
      <div>
        <h4 class="text-sm font-semibold mb-4 uppercase tracking-wider">${section}</h4>
        <ul class="space-y-2">
          <li><a href="#" class="text-gray-400 hover:text-white text-sm">Link 1</a></li>
          <li><a href="#" class="text-gray-400 hover:text-white text-sm">Link 2</a></li>
          <li><a href="#" class="text-gray-400 hover:text-white text-sm">Link 3</a></li>
        </ul>
      </div>`).join('')}
    </div>
    ${includeNewsletter ? `
    <div class="mt-8 pt-8 border-t border-gray-800">
      <div class="max-w-md">
        <h4 class="text-sm font-semibold mb-2">Subscribe to our newsletter</h4>
        <div class="flex">
          <input type="email" placeholder="Enter your email" class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-l-md text-sm" />
          <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-r-md text-sm font-medium">Subscribe</button>
        </div>
      </div>
    </div>` : ''}
    <div class="mt-8 pt-8 border-t border-gray-800 flex justify-between items-center">
      <p class="text-gray-400 text-sm">&copy; 2024 ${brandName}. All rights reserved.</p>
      ${socialLinks ? `
      <div class="flex space-x-4">
        ${socialLinks.map(platform => `<a href="#" class="text-gray-400 hover:text-white">${platform}</a>`).join('')}
      </div>` : ''}
    </div>
  </div>
</footer>`;

      setGeneratedFooter(footerCode);
      onFooterGenerated?.(footerCode);
      return `Generated footer for ${brandName} with ${footerLinks.length} link sections`;
    },
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <CopilotKit publicApiKey="ck_pub_aec8422e1c8947ceba500964ff3df565">
        <div className="flex">
          <main className="flex-1 p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-8">
              AI Header/Footer Generator
            </h1>

            <div className="space-y-8">
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-semibold mb-4">Generated Header</h2>
                {generatedHeader ? (
                  <div className="bg-gray-100 p-4 rounded border">
                    <pre className="text-sm overflow-x-auto">
                      <code>{generatedHeader}</code>
                    </pre>
                  </div>
                ) : (
                  <p className="text-gray-500">No header generated yet. Use the sidebar to create one!</p>
                )}
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-semibold mb-4">Generated Footer</h2>
                {generatedFooter ? (
                  <div className="bg-gray-100 p-4 rounded border">
                    <pre className="text-sm overflow-x-auto">
                      <code>{generatedFooter}</code>
                    </pre>
                  </div>
                ) : (
                  <p className="text-gray-500">No footer generated yet. Use the sidebar to create one!</p>
                )}
              </div>
            </div>
          </main>

          <CopilotSidebar
            defaultOpen={true}
            instructions="You are an expert UI/UX designer. Help users generate beautiful, responsive header and footer components. Ask about their brand, navigation needs, and styling preferences to create custom components."
          />
        </div>
      </CopilotKit>
    </div>
  );
}