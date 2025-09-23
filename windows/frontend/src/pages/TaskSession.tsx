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
import { useToast } from "@/hooks/use-toast";
import { Clock, User, Tag, FileText } from "lucide-react";
import { apiService } from "@/services/api";

const TaskSession = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [taskData, setTaskData] = useState<any>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isEndingSession, setIsEndingSession] = useState(false);

  useEffect(() => {
    // Get task data from localStorage
    const storedTask = localStorage.getItem("currentTask");
    if (!storedTask) {
      navigate("/task-form");
      return;
    }

    const task = JSON.parse(storedTask);
    setTaskData(task);

    // Start timer
    const startTime = new Date(task.startTime).getTime();
    const timer = setInterval(() => {
      const now = new Date().getTime();
      const elapsed = Math.floor((now - startTime) / 1000);
      setElapsedTime(elapsed);
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate]);

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${remainingSeconds
        .toString()
        .padStart(2, "0")}`;
    }
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  const handleEndSession = async () => {
    if (!taskData || isEndingSession) return;

    setIsEndingSession(true);

    try {
      // First, stop the interventions monitoring
      const stopResult = await apiService.stopInterventions();

      // Record session end data
      const endTime = new Date().toISOString();
      const sessionData = {
        ...taskData,
        endTime,
        actualDuration: elapsedTime,
        interventionsStopped: stopResult.status === "success",
      };

      localStorage.setItem("completedTask", JSON.stringify(sessionData));

      if (stopResult.status === "success") {
        toast({
          title: "Task session ended",
          description:
            "Monitoring stopped successfully. Please complete the assessment forms",
        });
      } else {
        toast({
          title: "Task session ended",
          description: `Session saved. ${stopResult.message}`,
          variant: "destructive",
        });
      }

      navigate("/task-results");
    } catch (error) {
      console.error("Error ending session:", error);

      // Still end the session even if stopping interventions fails
      const endTime = new Date().toISOString();
      const sessionData = {
        ...taskData,
        endTime,
        actualDuration: elapsedTime,
        interventionsStopped: false,
        error: "Failed to stop interventions",
      };

      localStorage.setItem("completedTask", JSON.stringify(sessionData));

      toast({
        title: "Task session ended",
        description:
          "Session saved, but failed to stop monitoring. Please check manually.",
        variant: "destructive",
      });

      navigate("/task-results");
    } finally {
      setIsEndingSession(false);
    }
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
      <Card className="w-full max-w-2xl shadow-sm border-border/50">
        <CardHeader className="text-center space-y-2">
          <CardTitle className="text-2xl font-normal text-text-primary">
            Task in Progress
          </CardTitle>
          <CardDescription className="text-text-secondary">
            Complete your task and click end session when finished
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Timer Display */}
          <div className="text-center p-6 bg-surface-elevated rounded-lg border border-border/50">
            <div className="text-4xl font-mono text-accent mb-2">
              {formatTime(elapsedTime)}
            </div>
            <p className="text-sm text-text-secondary">Elapsed Time</p>
          </div>

          {/* Task Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center space-x-3 p-3 bg-surface-elevated rounded-lg border border-border/50">
              <User className="w-5 h-5 text-text-secondary" />
              <div>
                <p className="text-sm text-text-secondary">Participant</p>
                <p className="font-medium text-text-primary">{taskData.name}</p>
              </div>
            </div>

            <div className="flex items-center space-x-3 p-3 bg-surface-elevated rounded-lg border border-border/50">
              <Tag className="w-5 h-5 text-text-secondary" />
              <div>
                <p className="text-sm text-text-secondary">Category</p>
                <p className="font-medium text-text-primary capitalize">
                  {Array.isArray(taskData.category)
                    ? taskData.category.join(", ")
                    : taskData.category}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-start space-x-3 p-3 bg-surface-elevated rounded-lg border border-border/50">
            <FileText className="w-5 h-5 text-text-secondary mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-text-secondary">Task Description</p>
              <p className="text-text-primary">{taskData.taskDescription}</p>
            </div>
          </div>

          <div className="flex items-center space-x-3 p-3 bg-surface-elevated rounded-lg border border-border/50">
            <Clock className="w-5 h-5 text-text-secondary" />
            <div>
              <p className="text-sm text-text-secondary">Estimated Duration</p>
              <p className="font-medium text-text-primary">
                {taskData.estimatedTime} minutes
              </p>
            </div>
          </div>

          {/* Instructions */}
          <div className="p-4 bg-muted rounded-lg border border-border/50">
            <h3 className="font-medium text-text-primary mb-2">Instructions</h3>
            <ul className="text-sm text-text-secondary space-y-1">
              <li>• Focus on your task and work at your normal pace</li>
              <li>• The timer is for reference only</li>
              <li>• Click "End Session" when you complete your task</li>
            </ul>
          </div>

          <div className="pt-4">
            <Button
              onClick={handleEndSession}
              disabled={isEndingSession}
              className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground disabled:opacity-50"
              size="lg"
            >
              {isEndingSession ? "Ending Session..." : "End Task Session"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TaskSession;
