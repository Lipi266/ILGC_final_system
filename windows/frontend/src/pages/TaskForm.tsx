import { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/hooks/use-toast";
import { apiService } from "@/services/api";

const TaskForm = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [formData, setFormData] = useState({
    name: "",
    participantId: "",
    batch: "",
    category: [] as string[], // Changed to array for multiple selections
    taskDescription: "",
    estimatedTime: "",
    systemType: "",
  });

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleCategoryChange = (category: string, checked: boolean) => {
    setFormData((prev) => ({
      ...prev,
      category: checked
        ? [...prev.category, category]
        : prev.category.filter((c) => c !== category),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate form
    if (
      !formData.name ||
      !formData.participantId ||
      !formData.batch ||
      formData.category.length === 0 || // Changed to check array length
      !formData.taskDescription ||
      !formData.estimatedTime ||
      !formData.systemType
    ) {
      toast({
        title: "Please fill in all fields",
        variant: "destructive",
      });
      return;
    }

    // Validate participant ID is a number
    if (!/^\d+$/.test(formData.participantId)) {
      toast({
        title: "Invalid Participant ID",
        description: "Participant ID must be a number",
        variant: "destructive",
      });
      return;
    }

    try {
      // Prepare task data with timestamp
      const taskData = {
        ...formData,
        startTime: new Date().toISOString(),
      };

      // Store task data in localStorage for later use
      localStorage.setItem("currentTask", JSON.stringify(taskData));

      // Save to backend and start interventions
      const result = await apiService.saveTaskDetailsAndStart(taskData);

      toast({
        title: "Task session started",
        description: result.interventionsStarted
          ? "Task details saved and monitoring started!"
          : "Task details saved. Good luck with your task!",
      });

      navigate("/task-session");
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to start task session. Please try again.",
        variant: "destructive",
      });
      console.error("Error starting task session:", error);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl shadow-sm border-border/50">
        <CardHeader className="text-center space-y-2">
          <CardTitle className="text-2xl font-normal text-text-primary">
            Task Setup
          </CardTitle>
          <CardDescription className="text-text-secondary">
            Please provide details about your upcoming task
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label
                htmlFor="name"
                className="text-sm font-medium text-text-primary"
              >
                Full Name
              </Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => handleInputChange("name", e.target.value)}
                className="border-border/50 focus:border-accent"
                placeholder="Enter your full name"
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="participantId"
                className="text-sm font-medium text-text-primary"
              >
                Participant ID
              </Label>
              <Input
                id="participantId"
                type="number"
                value={formData.participantId}
                onChange={(e) =>
                  handleInputChange("participantId", e.target.value)
                }
                className="border-border/50 focus:border-accent"
                placeholder="Enter your participant ID (numbers only)"
                min="1"
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="batch"
                className="text-sm font-medium text-text-primary"
              >
                Batch
              </Label>
              <Select
                onValueChange={(value) => handleInputChange("batch", value)}
                value={formData.batch}
              >
                <SelectTrigger
                  className="border-border/50 focus:border-accent"
                  id="batch"
                >
                  <SelectValue placeholder="Select your batch" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="UG26">UG26</SelectItem>
                  <SelectItem value="UG27">UG27</SelectItem>
                  <SelectItem value="UG28">UG28</SelectItem>
                  <SelectItem value="UG29">UG29</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium text-text-primary">
                System Type
              </Label>
              <RadioGroup
                value={formData.systemType}
                onValueChange={(value) =>
                  handleInputChange("systemType", value)
                }
                className="space-y-2"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="system1" id="system1" />
                  <Label
                    htmlFor="system1"
                    className="text-sm font-normal cursor-pointer"
                  >
                    System 1
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="system2" id="system2" />
                  <Label
                    htmlFor="system2"
                    className="text-sm font-normal cursor-pointer"
                  >
                    System 2
                  </Label>
                </div>
              </RadioGroup>
              <p className="text-xs text-muted-foreground">
                {formData.systemType === "system1"
                  ? "You've chosen System 1"
                  : formData.systemType === "system2"
                  ? "You've chose System 2"
                  : "Please select the system type for this session."}
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium text-text-primary">
                Task Categories (Select all that apply)
              </Label>
              <div className="space-y-3 p-4 border border-border/50 rounded-lg">
                {[
                  { value: "studying", label: "Studying" },
                  { value: "research-writing", label: "Research/Writing" },
                  { value: "coding", label: "Coding" },
                  { value: "social-media", label: "Social Media Work" },
                ].map((category) => (
                  <div
                    key={category.value}
                    className="flex items-center space-x-2"
                  >
                    <Checkbox
                      id={category.value}
                      checked={formData.category.includes(category.value)}
                      onCheckedChange={(checked) =>
                        handleCategoryChange(category.value, checked as boolean)
                      }
                    />
                    <Label
                      htmlFor={category.value}
                      className="text-sm font-normal cursor-pointer"
                    >
                      {category.label}
                    </Label>
                  </div>
                ))}
              </div>
              {formData.category.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Selected: {formData.category.join(", ")}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="description"
                className="text-sm font-medium text-text-primary"
              >
                Task Description
              </Label>
              <Textarea
                id="description"
                value={formData.taskDescription}
                onChange={(e) =>
                  handleInputChange("taskDescription", e.target.value)
                }
                className="border-border/50 focus:border-accent min-h-[100px]"
                placeholder="Briefly describe what task you will be performing..."
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium text-text-primary">
                Estimated Time (minutes)
              </Label>
              <Select
                onValueChange={(value) =>
                  handleInputChange("estimatedTime", value)
                }
              >
                <SelectTrigger className="border-border/50 focus:border-accent">
                  <SelectValue placeholder="How long will this take?" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5 minutes</SelectItem>
                  <SelectItem value="10">10 minutes</SelectItem>
                  <SelectItem value="15">15 minutes</SelectItem>
                  <SelectItem value="30">30 minutes</SelectItem>
                  <SelectItem value="45">45 minutes</SelectItem>
                  <SelectItem value="60">1 hour</SelectItem>
                  <SelectItem value="90">1.5 hours</SelectItem>
                  <SelectItem value="120">2 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="pt-4">
              <Button
                type="submit"
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
                size="lg"
              >
                Start Task
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default TaskForm;
