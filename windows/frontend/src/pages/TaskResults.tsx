import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ExternalLink } from "lucide-react";

const TaskResults = () => {
  const navigate = useNavigate();
  const [taskData, setTaskData] = useState<any>(null);

  useEffect(() => {
    const storedTask = localStorage.getItem("completedTask");
    if (!storedTask) {
      navigate("/");
      return;
    }
    setTaskData(JSON.parse(storedTask));
  }, [navigate]);

  const handleFeedbackClick = () => {
    // Clean up localStorage
    localStorage.removeItem("currentTask");
    localStorage.removeItem("completedTask");

    // Open Microsoft Forms in new tab
    window.open(
      "https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=M4x5RUMbAUy_PtjWVdM4nKa3h3dGz11PvcqBDTUv2SFUM040RUVRRldSTUVYV0kzMkVWVDc0VjRUVS4u"
    );

    // Navigate back to home
    navigate("/");
  };

  if (!taskData) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-sm border-border/50">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-normal text-text-primary">
            Task Completed!
          </CardTitle>
          <CardDescription className="text-text-secondary">
            Thank you for completing the task. Please provide your feedback.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <Button
            onClick={handleFeedbackClick}
            className="px-8 py-3 bg-primary hover:bg-primary/90 text-primary-foreground flex items-center gap-2 mx-auto"
            size="lg"
          >
            <ExternalLink className="w-4 h-4" />
            Feedback Form
          </Button>
          <p className="text-xs text-text-tertiary mt-4">
            This will open the feedback form in a new tab
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default TaskResults;
