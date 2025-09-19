// Update this page (the content is just a fallback if you fail to update the page)

import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Brain, BarChart3 } from "lucide-react";

const Index = () => {
  const navigate = useNavigate();

  const handleStartSession = () => {
    navigate('/task-form');
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <Card className="w-full max-w-lg shadow-sm border-border/50">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-accent/10 rounded-full flex items-center justify-center">
            <Brain className="w-8 h-8 text-accent" />
          </div>
          <div>
            <CardTitle className="text-3xl font-normal text-text-primary mb-2">
              ILGC Research Study
            </CardTitle>
            <CardDescription className="text-text-secondary text-base">
              Welcome to our ILGC research study! 
            </CardDescription>
            <CardDescription className="text-text-secondary text-base">
            Thank you for helping us out :)
            </CardDescription>
            <CardDescription className="text-text-secondary text-base">
            Click below to begin a new session.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <Button 
            onClick={handleStartSession}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
            size="lg"
          >
            Start New Session
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default Index;
