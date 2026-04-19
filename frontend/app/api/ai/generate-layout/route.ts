import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { description, context } = await request.json();

    // Call the ai_assistant service for layout generation
    const aiResponse = await fetch(`${process.env.AI_ASSISTANT_URL || 'http://localhost:8000'}/api/generate-layout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        description,
        context: context || 'ekioba-marketplace',
        format: 'react-layout'
      }),
    });

    if (!aiResponse.ok) {
      throw new Error(`AI service responded with ${aiResponse.status}`);
    }

    const aiData = await aiResponse.json();

    return NextResponse.json({
      layout: aiData.layout || [],
    });
  } catch (error) {
    console.error('Error in generate-layout API:', error);

    // Return a fallback layout
    return NextResponse.json({
      layout: [
        {
          type: 'div',
          props: {
            className: 'fallback-layout p-4 border rounded bg-gray-100',
            children: 'Generated Layout (AI unavailable)',
          },
        },
      ],
    });
  }
}