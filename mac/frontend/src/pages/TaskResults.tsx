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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/hooks/use-toast";
import { Upload, FileText, Brain, Star } from "lucide-react";
import { apiService } from "@/services/api";

const TaskResults = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [taskData, setTaskData] = useState<any>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [nasaTlx, setNasaTlx] = useState({
    mental: "",
    physical: "",
    temporal: "",
    performance: "",
    effort: "",
    frustration: "",
  });
  const [likertResponses, setLikertResponses] = useState({
    accuracy: "",
    effectiveness: "",
    personalisation: "",
  });

  useEffect(() => {
    const storedTask = localStorage.getItem("completedTask");
    if (!storedTask) {
      navigate("/");
      return;
    }
    setTaskData(JSON.parse(storedTask));
  }, [navigate]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile(file);
    }
  };

  const handleNasaTlxChange = (field: string, value: string) => {
    setNasaTlx((prev) => ({ ...prev, [field]: value }));
  };

  const handleLikertChange = (field: string, value: string) => {
    setLikertResponses((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all forms are filled
    const nasaTlxComplete = Object.values(nasaTlx).every((v) => v !== "");
    const likertComplete = Object.values(likertResponses).every(
      (v) => v !== ""
    );

    if (!nasaTlxComplete || !likertComplete) {
      toast({
        title: "Please complete all assessment forms",
        variant: "destructive",
      });
      return;
    }

    if (!taskData?.participantId) {
      toast({
        title: "Participant ID missing",
        description: "Cannot save assessment without participant ID",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      // Prepare assessment data
      const assessmentData = {
        participantId: taskData.participantId,
        batch: taskData.batch,
        category: taskData.category,
        taskDescription: taskData.taskDescription,
        name: taskData.name,
        estimatedTime: taskData.estimatedTime,
        file: uploadedFile?.name || "No file uploaded",
        nasaTlx,
        likertResponses,
        submittedAt: new Date().toISOString(),
      };

      // Save assessment via API
      const result = await apiService.saveAssessment(assessmentData);

      // Store results locally as backup
      localStorage.setItem("sessionResults", JSON.stringify(assessmentData));
      localStorage.removeItem("currentTask");
      localStorage.removeItem("completedTask");

      toast({
        title: "Assessment completed!",
        description: result.isNewFile
          ? "Assessment saved successfully"
          : `Assessment appended (${result.totalEntries} total entries)`,
      });

      navigate("/");
    } catch (error: any) {
      console.error("Failed to save assessment:", error);
      toast({
        title: "Failed to save assessment",
        description: error.message || "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!taskData) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        Loading...
      </div>
    );
  }

  const renderLikertScale = (label: string, field: string) => (
    <div className="space-y-3">
      <Label className="text-sm font-medium text-text-primary">{label}</Label>
      <RadioGroup
        value={likertResponses[field as keyof typeof likertResponses]}
        onValueChange={(value) => handleLikertChange(field, value)}
        className="flex justify-between"
      >
        {[1, 2, 3, 4, 5].map((num) => (
          <div key={num} className="flex flex-col items-center space-y-2">
            <RadioGroupItem value={num.toString()} id={`${field}-${num}`} />
            <Label
              htmlFor={`${field}-${num}`}
              className="text-xs text-text-secondary"
            >
              {num}
            </Label>
          </div>
        ))}
      </RadioGroup>
      <div className="flex justify-between text-xs text-text-tertiary">
        <span>Strongly Disagree</span>
        <span>Strongly Agree</span>
      </div>
    </div>
  );

  const renderNasaTlxScale = (
    label: string,
    description: string,
    field: string
  ) => (
    <div className="space-y-3">
      <div>
        <Label className="text-sm font-medium text-text-primary">{label}</Label>
        <p className="text-xs text-text-secondary mt-1">{description}</p>
      </div>
      <RadioGroup
        value={nasaTlx[field as keyof typeof nasaTlx]}
        onValueChange={(value) => handleNasaTlxChange(field, value)}
        className="flex justify-between"
      >
        {Array.from({ length: 11 }, (_, i) => i).map((num) => (
          <div key={num} className="flex flex-col items-center space-y-2">
            <RadioGroupItem value={num.toString()} id={`${field}-${num}`} />
            <Label
              htmlFor={`${field}-${num}`}
              className="text-xs text-text-secondary"
            >
              {num}
            </Label>
          </div>
        ))}
      </RadioGroup>
      <div className="flex justify-between text-xs text-text-tertiary">
        <span>Very Low</span>
        <span>Very High</span>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface p-4">
      <div className="max-w-4xl mx-auto space-y-8">
        <Card className="shadow-sm border-border/50">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-normal text-text-primary">
              Task Assessment
            </CardTitle>
            <CardDescription className="text-text-secondary">
              Please complete the following assessment forms
            </CardDescription>
          </CardHeader>
        </Card>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* File Upload Section */}
          <Card className="shadow-sm border-border/50">
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Upload className="w-5 h-5 text-accent" />
                <CardTitle className="text-lg font-medium">
                  Upload Your Work
                </CardTitle>
              </div>
              <CardDescription>
                Upload any files or documents you created during the task
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
                <Input
                  type="file"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="file-upload"
                  accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.zip,.ipynb,.cpp,.c,.h,.hpp,.html,.htm,.css,.js,.ts,.jsx,.tsx,.py,.java,.rb,.php,.go,.rs,.swift,.kt,.scala,.r,.m,.sql,.json,.xml,.yaml,.yml,.md,.sh,.bat,.ps1,.dockerfile,.dockerignore,.gitignore,.env,.config,.conf,.ini,.cfg,.log,.csv,.xlsx,.xls"
                />
                <Label htmlFor="file-upload" className="cursor-pointer">
                  <div className="space-y-2">
                    <FileText className="w-8 h-8 mx-auto text-text-secondary" />
                    <p className="text-sm text-text-primary">
                      {uploadedFile
                        ? uploadedFile.name
                        : "Click to upload file"}
                    </p>
                    <p className="text-xs text-text-secondary">
                      PDF, DOC, TXT, Images, ZIP, Code files (.ipynb, .cpp, .c,
                      .html, .py, .js, etc.), and more
                    </p>
                  </div>
                </Label>
              </div>
            </CardContent>
          </Card>

          {/* NASA TLX Assessment */}
          <Card className="shadow-sm border-border/50">
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Brain className="w-5 h-5 text-accent" />
                <CardTitle className="text-lg font-medium">
                  NASA Task Load Index (TLX)
                </CardTitle>
              </div>
              <CardDescription>
                Rate each dimension of workload on a scale from 0-20
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {renderNasaTlxScale(
                "Mental Demand",
                "How much mental and perceptual activity was required for this task?",
                "mental"
              )}
              {renderNasaTlxScale(
                "Physical Demand",
                " How much physical activity was required for this task?",
                "physical"
              )}
              {renderNasaTlxScale(
                "Temporal Demand",
                "How hurried or rushed was the pace of the task?",
                "temporal"
              )}
              {renderNasaTlxScale(
                "Performance",
                "How successful do you think you were in accomplishing the task?",
                "performance"
              )}
              {renderNasaTlxScale(
                "Effort",
                "How hard did you have to work to accomplish your level of performance?",
                "effort"
              )}
              {renderNasaTlxScale(
                "Frustration",
                "How insecure, discouraged, irritated, stressed, and annoyed were you?",
                "frustration"
              )}
            </CardContent>
          </Card>

          {/* Likert Scale Assessment */}
          <Card className="shadow-sm border-border/50">
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Star className="w-5 h-5 text-accent" />
                <CardTitle className="text-lg font-medium">
                  Task Evaluation
                </CardTitle>
              </div>
              <CardDescription>
                Rate your agreement with the following statements (1-5 scale)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {renderLikertScale(
                "How well were we able to catch your distraction?",
                "accuracy"
              )}
              {renderLikertScale(
                "How effective were the interventions?",
                "effectiveness"
              )}
              {renderLikertScale(
                "How personalised were the distractions",
                "personalisation"
              )}
            </CardContent>
          </Card>

          <div className="flex justify-center">
            <Button
              type="submit"
              className="px-8 bg-primary hover:bg-primary/90 text-primary-foreground"
              size="lg"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Saving Assessment..." : "Submit Assessment"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TaskResults;
