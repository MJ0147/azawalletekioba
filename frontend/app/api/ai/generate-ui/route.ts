import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { description, componentType, context } = await request.json();

    // Call the ai_assistant service
    const aiResponse = await fetch(`${process.env.AI_ASSISTANT_URL || 'http://localhost:8000'}/api/generate-ui`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        component_type: componentType,
        theme: 'modern',
        features: ['responsive', 'accessible'],
        brand_name: 'Ekioba',
        description: description
      }),
    });

    if (!aiResponse.ok) {
      throw new Error(`AI service responded with ${aiResponse.status}`);
    }

    const aiData = await aiResponse.json();

    return NextResponse.json({
      component: aiData.component || {
        type: componentType,
        props: {
          className: 'generated-component bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600',
          children: description,
        },
      },
    });
  } catch (error) {
    console.error('Error in generate-ui API:', error);

    // Return a fallback component
    return NextResponse.json({
      component: {
        type: 'button',
        props: {
          className: 'generated-component bg-gray-500 text-white px-4 py-2 rounded',
          children: 'Generated Component (AI unavailable)',
        },
      },
    });
  }
}