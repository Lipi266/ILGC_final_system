// API service for communicating with the Flask backend
class ApiService {
  constructor() {
    this.baseURL = 'http://localhost:5000/api';
  }

  async saveTaskDetailsAndStart(taskData) {
    try {
      const response = await fetch(`${this.baseURL}/save-task-details`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(taskData)
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.message || 'Failed to save task details');
      }
      
      return result;
    } catch (error) {
      console.error('Error saving task details:', error);
      throw error;
    }
  }

  async stopInterventions() {
    try {
      const response = await fetch(`${this.baseURL}/stop-interventions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.message || 'Failed to stop interventions');
      }
      
      return result;
    } catch (error) {
      console.error('Error stopping interventions:', error);
      throw error;
    }
  }

  async saveAssessment(assessmentData) {
    try {
      const response = await fetch(`${this.baseURL}/save-assessment`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(assessmentData)
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.message || 'Failed to save assessment');
      }
      
      return result;
    } catch (error) {
      console.error('Error saving assessment:', error);
      throw error;
    }
  }

  async saveFeedback(feedbackData) {
    try {
      const response = await fetch(`${this.baseURL}/save-feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(feedbackData)
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.message || 'Failed to save feedback');
      }
      
      return result;
    } catch (error) {
      console.error('Error saving feedback:', error);
      throw error;
    }
  }

  async getStatus() {
    try {
      const response = await fetch(`${this.baseURL}/status`);
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error('Failed to get status');
      }
      
      return result;
    } catch (error) {
      console.error('Error getting status:', error);
      throw error;
    }
  }

  async getTaskDetails() {
    try {
      const response = await fetch(`${this.baseURL}/get-task-details`);
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error('Failed to get task details');
      }
      
      return result;
    } catch (error) {
      console.error('Error getting task details:', error);
      throw error;
    }
  }
}

export const apiService = new ApiService();
