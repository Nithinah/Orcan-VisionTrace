import React, { useState, useEffect } from 'react';
import { Plus, Search, ChevronDown, Check, X, UploadCloud, File, Trash2, Cloud, HardDrive, Eye, Wallet, Clock, BarChart, Settings, ArrowLeft, Key, Folder, ExternalLink, LogOut, Mail, Lock, User, AlertCircle, Globe, Archive } from 'lucide-react';

// --- BACKEND API INTEGRATION ---

const API_BASE_URL = 'http://127.0.0.1:8020/api';

// Helper function to get auth headers
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Auth API calls
export const authAPI = {
  signup: async (name, email, password) => {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Signup failed');
    }
    
    return response.json();
  },

  login: async (email, password) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    
    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    return data;
  },

  getCurrentUser: async () => {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get user info');
    }
    
    return response.json();
  },

  logout: () => {
    localStorage.removeItem('token');
  }
};

// Data Sources API calls

export const dataSourceAPI = {
  connectS3: async (bucketName, folderPath, accessKey, secretKey) => {
    const formData = new FormData();
    formData.append('bucket_name', bucketName);
    formData.append('folder_path', folderPath || '');
    formData.append('access_key', accessKey);
    formData.append('secret_key', secretKey);

    const response = await fetch(`${API_BASE_URL}/data-sources/s3/connect`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'S3 connection failed');
    }
    
    return response.json();
  },

  connectGDrive: async (folderLink) => {
    const response = await fetch(`${API_BASE_URL}/data-sources/gdrive/connect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        folder_link: folderLink
      }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Google Drive connection failed');
    }
    
    return response.json();
  },

  uploadFiles: async (files) => {
    const formData = new FormData();
    for (let file of files) {
      formData.append('files', file);
    }
    
    const response = await fetch(`${API_BASE_URL}/data-sources/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'File upload failed');
    }
    
    return response.json();
  },

  getDataSources: async () => {
    const response = await fetch(`${API_BASE_URL}/data-sources`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch data sources');
    }
    
    return response.json();
  }
};

export const s3API = {
  connectS3: async (bucketName, folderPath, accessKey, secretKey, region) => {
    // Validate region is provided
    if (!region || region === '') {
      throw new Error('AWS region is required. Please select a region or use auto-detect.');
    }

    const formData = new FormData();
    formData.append('bucket_name', bucketName);
    formData.append('folder_path', folderPath || '');
    formData.append('access_key', accessKey);
    formData.append('secret_key', secretKey);
    formData.append('region', region);

    const response = await fetch(`${API_BASE_URL}/data-sources/s3/connect`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'S3 connection failed');
    }
    
    return response.json();
  },

  calculateCost: async (s3Config) => {
    const formData = new FormData();
    formData.append('bucket_name', s3Config.bucket_name);
    formData.append('folder_path', s3Config.folder_path || '');
    formData.append('access_key', s3Config.access_key);
    formData.append('secret_key', s3Config.secret_key);
    formData.append('region', s3Config.region);

    const response = await fetch(`${API_BASE_URL}/s3/calculate-cost`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Cost calculation failed');
    }
    
    return response.json();
  },

  startIndexing: async (s3Config, imageSetId) => {
    const formData = new FormData();
    formData.append('bucket_name', s3Config.bucket_name);
    formData.append('folder_path', s3Config.folder_path || '');
    formData.append('access_key', s3Config.access_key);
    formData.append('secret_key', s3Config.secret_key);
    formData.append('region', s3Config.region);
    formData.append('image_set_id', imageSetId);

    const response = await fetch(`${API_BASE_URL}/s3/start-indexing`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Indexing failed to start');
    }
    
    return response.json();
  },

  searchImages: async (imageFile, imageSetIds) => {
    const formData = new FormData();
    formData.append('file', imageFile);
    formData.append('image_set_ids', imageSetIds.join(','));
    
    const response = await fetch(`${API_BASE_URL}/s3/search`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Search failed');
    }
    
    return response.json();
  },
  
  detectRegion: async (bucketName, accessKey, secretKey) => {
    const formData = new FormData();
    formData.append('bucket_name', bucketName);
    formData.append('access_key', accessKey);
    formData.append('secret_key', secretKey);

    const response = await fetch(`${API_BASE_URL}/s3/detect-region`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Region detection failed');
    }
    
    return response.json();
  }
};



// Image Sets API calls
export const imageSetAPI = {
  getImageSets: async () => {
    const response = await fetch(`${API_BASE_URL}/image-sets`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch image sets');
    }
    
    return response.json();
  },

  createImageSet: async (name, description) => {
    const response = await fetch(`${API_BASE_URL}/image-sets`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({ name, description }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create image set');
    }
    
    return response.json();
  },

  deleteImageSet: async (imageSetId) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete image set');
    }
    
    return response.json();
  },

  calculateCost: async (imageSetId, dataSourceIds) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/calculate-cost`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(dataSourceIds),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Cost calculation failed');
    }
    
    return response.json();
  },

  startIndexing: async (imageSetId, dataSourceIds) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/start-indexing`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(dataSourceIds),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Indexing failed to start');
    }
    
    return response.json();
  },
  
  uploadFolder: async (imageSetId, zipFile) => {
    const formData = new FormData();
    formData.append('file', zipFile);
    
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/upload-folder`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Folder upload failed');
    }
    
    return response.json();
  },

  calculateCostBulk: async (imageSetId) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/calculate-cost-bulk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Cost calculation failed');
    }
    
    return response.json();
  },

  startIndexingBulk: async (imageSetId) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/start-indexing-bulk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Indexing failed to start');
    }
    
    return response.json();
  },
  
  getProgress: async (imageSetId) => {
    const response = await fetch(`${API_BASE_URL}/image-sets/${imageSetId}/progress`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get progress');
    }
    
    return response.json();
  },
};



// Search API calls
export const searchAPI = {
  searchImages: async (imageFile, imageSetIds) => {
    const formData = new FormData();
    formData.append('file', imageFile);
    formData.append('image_set_ids', imageSetIds.join(','));
    
    const response = await fetch(`${API_BASE_URL}/search`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Search failed');
    }
    
    return response.json();
  }
};

// Add this new API object after searchAPI
export const searchHistoryAPI = {
  getHistory: async () => {
    const response = await fetch(`${API_BASE_URL}/search-history`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch search history');
    }
    
    return response.json();
  },

  deleteHistoryItem: async (searchId) => {
    const response = await fetch(`${API_BASE_URL}/search-history/${searchId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete search history item');
    }
    
    return response.json();
  },

  clearHistory: async () => {
    const response = await fetch(`${API_BASE_URL}/search-history`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to clear search history');
    }
    
    return response.json();
  },
  
  getSearchResults: async (searchId) => {
    const response = await fetch(`${API_BASE_URL}/search-history/${searchId}/results`, {
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch search results');
    }
    
    return response.json();
  }
};

// Health check
export const healthCheck = async () => {
  const response = await fetch(`${API_BASE_URL}/health`);
  return response.json();
};

// --- AUTHENTICATION COMPONENTS ---

const GoogleIcon = () => (
  <svg className="w-5 h-5 mr-3" viewBox="0 0 48 48">
    <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12s5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24s8.955,20,20,20s20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"></path>
    <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"></path>
    <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"></path>
    <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571l6.19,5.238C42.022,35.372,44,30.038,44,24C44,22.659,43.862,21.35,43.611,20.083z"></path>
  </svg>
);

const AuthPage = ({ onLogin }) => {
    const [isLoginView, setIsLoginView] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        const formData = new FormData(e.target);
        const email = formData.get('email');
        const password = formData.get('password');
        const name = formData.get('name');

        try {
            if (isLoginView) {
                const response = await authAPI.login(email, password);
                console.log('Login successful:', response);
                onLogin();
            } else {
                const signupResponse = await authAPI.signup(name, email, password);
                console.log('Signup successful:', signupResponse);
                // After successful signup, switch to login view
                setIsLoginView(true);
                setError('');
                // Show success message
                alert('Account created successfully! Please login with your credentials.');
            }
        } catch (err) {
            console.error('Auth error:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleLogin = async () => {
        setLoading(true);
        setError('');
        
        try {
            // For demo purposes, we'll simulate Google login
            // In a real implementation, you'd integrate with Google OAuth
            alert('Google Sign-In would be implemented here with Google OAuth');
            // For now, you can manually login with existing credentials
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
            <div className="w-full max-w-4xl mx-auto bg-white rounded-2xl shadow-xl flex overflow-hidden">
                {/* Left Panel */}
                <div className="w-1/2 bg-blue-600 text-white p-12 flex-col justify-between hidden md:flex">
                    <div>
                        <div className="flex items-center text-white mb-8">
                            <Eye size={36} />
                            <span className="text-2xl font-bold ml-3">Orcan VisionTrace</span>
                        </div>
                        <h1 className="text-4xl font-bold mb-4">Unlock Visual Insights.</h1>
                        <p className="text-blue-200 mb-6">
                            The enterprise-grade reverse image search platform. Index millions of images and find what you're looking for in seconds.
                        </p>
                    </div>
                    <div className="text-sm text-blue-300 mt-8">
                        &copy; {new Date().getFullYear()} Orcan Intelligence. All rights reserved.
                    </div>
                </div>

                {/* Right Panel (Form) */}
                <div className="w-full md:w-1/2 p-8 sm:p-12">
                    <h2 className="text-3xl font-bold text-gray-800 mb-2">
                        {isLoginView ? 'Welcome Back' : 'Create Account'}
                    </h2>
                    <p className="text-gray-500 mb-8">
                        {isLoginView ? 'Please sign in to continue.' : 'Get started with your free account.'}
                    </p>

                    {error && (
                        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
                            <AlertCircle size={16} className="mr-2" />
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        <div className="space-y-5">
                            {!isLoginView && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                                    <div className="relative">
                                        <input 
                                            name="name" 
                                            type="text" 
                                            required 
                                            className="w-full p-3 pl-10 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500" 
                                            placeholder="John Doe" 
                                        />
                                        <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                                    </div>
                                </div>
                            )}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                <div className="relative">
                                    <input 
                                        name="email" 
                                        type="email" 
                                        required 
                                        className="w-full p-3 pl-10 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500" 
                                        placeholder="you@example.com" 
                                    />
                                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                                <div className="relative">
                                    <input 
                                        name="password" 
                                        type="password" 
                                        required 
                                        className="w-full p-3 pl-10 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500" 
                                        placeholder="••••••••" 
                                    />
                                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                                </div>
                            </div>
                        </div>

                        {isLoginView && (
                            <div className="text-right mt-2">
                                <a href="#" className="text-sm font-medium text-blue-600 hover:text-blue-500">Forgot password?</a>
                            </div>
                        )}

                        <div className="mt-8">
                            <button 
                                type="submit" 
                                disabled={loading} 
                                className="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                            >
                                {loading ? 'Please wait...' : (isLoginView ? 'Sign In' : 'Sign Up')}
                            </button>
                        </div>
                    </form>

                    <div className="mt-8 text-center text-sm">
                        <p className="text-gray-500">
                            {isLoginView ? "Don't have an account?" : "Already have an account?"}
                            <button 
                                onClick={() => setIsLoginView(!isLoginView)} 
                                className="font-medium text-blue-600 hover:text-blue-500 ml-1"
                            >
                                {isLoginView ? 'Sign up' : 'Sign in'}
                            </button>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

// --- MAIN APPLICATION COMPONENTS ---

// Helper Components
const Icon = ({ type, className = "" }) => {
  const commonClass = `inline-block mr-2 ${className}`;
  if (type === 's3' || type === 's3_aws') return <Cloud className={`${commonClass} text-orange-500`} size={20} />;
  if (type === 'gdrive') return <HardDrive className={`${commonClass} text-blue-500`} size={20} />;
  if (type === 'bulk_upload') return <Archive className={`${commonClass} text-green-500`} size={20} />;
  if (type === 'upload') return <UploadCloud className={commonClass} size={20} />;
  return <File className={commonClass} size={20} />;
};

const SourceTypeBadge = ({ sourceType, sourceDisplay, className = "" }) => {
  const getSourceConfig = (type) => {
    switch (type) {
      case 's3_aws':
        return {
          icon: <Cloud size={14} className="mr-1" />,
          bgColor: 'bg-orange-100',
          textColor: 'text-orange-800',
          label: 'AWS S3'
        };
      case 'bulk_upload':
        return {
          icon: <Archive size={14} className="mr-1" />,
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          label: 'Bulk Upload'
        };
      case 'gdrive':
        return {
          icon: <HardDrive size={14} className="mr-1" />,
          bgColor: 'bg-blue-100',
          textColor: 'text-blue-800',
          label: 'Google Drive'
        };
      default:
        return {
          icon: <File size={14} className="mr-1" />,
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-800',
          label: 'Unknown'
        };
    }
  };

  const config = getSourceConfig(sourceType);

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full inline-flex items-center ${config.bgColor} ${config.textColor} ${className}`}>
      {config.icon}
      {config.label}
    </span>
  );
};

const StatusPill = ({ status }) => {
  const baseClasses = "px-3 py-1 text-xs font-medium rounded-full inline-flex items-center";
  let specificClasses = "";
  let icon = null;

  switch (status) {
    case 'ready':
    case 'Ready to Search':
      specificClasses = "bg-green-100 text-green-800";
      icon = <Check size={12} className="mr-1" />;
      break;
    case 'indexing':
    case 'Indexing':
      specificClasses = "bg-blue-100 text-blue-800 animate-pulse";
      icon = <Settings size={12} className="mr-1 animate-spin" />;
      break;
    case 'draft':
    case 'Draft':
      specificClasses = "bg-gray-100 text-gray-800";
      icon = <File size={12} className="mr-1" />;
      break;
    case 'error':
    case 'Error':
      specificClasses = "bg-red-100 text-red-800";
      icon = <X size={12} className="mr-1" />;
      break;
    default:
      specificClasses = "bg-gray-200 text-gray-700";
  }

  return <span className={`${baseClasses} ${specificClasses}`}>{icon}{status}</span>;
};

// Main Screens
const DashboardScreen = ({ imageSets, setView, setSelectedSet, user, credits, setCredits, onDeleteImageSet }) => {
  const [loading, setLoading] = useState(false);

  const handleAddCredits = () => {
    // Remove automatic credit addition - do nothing when clicked
    console.log('Add credits functionality would be implemented here');
    // Could open a billing/payment modal in a real application
  };

  const handleCreateNewImageSet = async () => {
    const newSet = {
      id: Date.now(),
      name: '',
      description: '',
      image_count: 0,
      status: 'draft',
      progress: 0,
      sources: []
    };
    setSelectedSet(newSet);
    setView('configureSet');
  };

  const handleDeleteImageSet = async (imageSetId, imageSetName) => {
    if (!window.confirm(`Are you sure you want to delete "${imageSetName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setLoading(true);
      await imageSetAPI.deleteImageSet(imageSetId);
      onDeleteImageSet(imageSetId);
    } catch (error) {
      alert(`Failed to delete image set: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const activeIndexingJobs = imageSets.filter(set => set.status === 'indexing').length;

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center">
            <div className="bg-blue-100 p-3 rounded-full mr-4">
              <Wallet className="text-blue-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Credits Remaining</p>
              <p className="text-2xl font-bold text-gray-800">{credits.toLocaleString()}</p>
            </div>
          </div>
          <button 
            onClick={handleAddCredits} 
            className="mt-4 w-full text-sm bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
          >
            + Add Credits
          </button>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center">
            <div className="bg-green-100 p-3 rounded-full mr-4">
              <Eye className="text-green-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Ready to Search</p>
              <p className="text-2xl font-bold text-gray-800">{imageSets.filter(s => s.status === 'ready').length} Sets</p>
            </div>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center">
            <div className="bg-yellow-100 p-3 rounded-full mr-4">
              <Clock className="text-yellow-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Active Indexing Jobs</p>
              <p className="text-2xl font-bold text-gray-800">{activeIndexingJobs}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
        <h1 className="text-2xl font-bold text-gray-800">My Image Sets</h1>
        <button
          onClick={handleCreateNewImageSet}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg inline-flex items-center transition-colors"
        >
          <Plus size={20} className="mr-2" />
          Create New Image Set
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="space-y-4 p-4">
          {imageSets.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">No image sets created yet. Create your first image set to get started.</p>
            </div>
          ) : (
            imageSets.map(set => (
              <div key={set.id} className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
                  <div className="flex-grow">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-lg font-bold text-gray-800">{set.name}</h3>
                      {set.id && (
                        <span className="px-2 py-1 text-xs font-mono bg-gray-100 text-gray-600 rounded">
                          ID: {set.id}
                        </span>
                      )}
                    </div>
                    {/* Enhanced source type display */}
                    <div className="flex items-center gap-2 mb-2">
                      <SourceTypeBadge 
                        sourceType={set.source_type} 
                        sourceDisplay={set.source_display} 
                      />
                      {set.source_display && (
                        <span className="text-xs text-gray-500 truncate max-w-xs">
                          {set.source_display}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{set.description}</p>
                    <p className="text-sm text-gray-500 mt-2 flex items-center">
                      <BarChart size={14} className="mr-1" />
                      {set.image_count?.toLocaleString() || 0} Images Indexed
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    <StatusPill status={set.status} />
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setSelectedSet(set); setView('configureSet'); }}
                        className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded-lg transition-colors"
                      >
                        Configure
                      </button>
                      <button
                        disabled={set.status !== 'ready'}
                        onClick={() => setView('search')}
                        className="text-sm bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                      >
                        Search This Set
                      </button>
                      <button
                        onClick={() => handleDeleteImageSet(set.id, set.name)}
                        disabled={loading}
                        className="text-sm bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-3 rounded-lg transition-colors disabled:opacity-50 flex items-center"
                        title="Delete Image Set"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
                {set.status === 'indexing' && (
                  <div className="mt-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm text-gray-600">Indexing Progress</span>
                      <span className="text-sm font-medium text-gray-800">{set.progress || 0}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                      <div 
                        className="bg-blue-600 h-2.5 rounded-full transition-all duration-300" 
                        style={{ width: `${set.progress || 0}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

// Modal Component for adding data sources - Complete with Auto-detect Region
const AddSourceModal = ({ show, onClose, setSources, onSourceAdded, imageSetId }) => {
    const [modalView, setModalView] = useState('select');
    const [bucketName, setBucketName] = useState('');
    const [folderPath, setFolderPath] = useState('');
    const [accessKey, setAccessKey] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [region, setRegion] = useState('');
    const [gdriveLink, setGdriveLink] = useState('');
    const [loading, setLoading] = useState(false);
    const [isDetectingRegion, setIsDetectingRegion] = useState(false);
    const [error, setError] = useState('');

    const handleDetectRegion = async () => {
        if (!bucketName || !accessKey || !secretKey) {
            setError('Please enter bucket name, access key, and secret key first');
            return;
        }

        setIsDetectingRegion(true);
        setError('');

        try {
            const response = await s3API.detectRegion(bucketName, accessKey, secretKey);
            setRegion(response.region);
            setError('');
        } catch (err) {
            setError(`Region detection failed: ${err.message}`);
        } finally {
            setIsDetectingRegion(false);
        }
    };

    const handleS3Connect = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        if (!region || region === '') {
            setError('Please select an AWS region or use auto-detect');
            setLoading(false);
            return;
        }

        try {
            const response = await s3API.connectS3(bucketName, folderPath, accessKey, secretKey, region);
            
            const newSource = {
                id: `s3_${Date.now()}`,
                type: 's3',
                path: `s3://${bucketName}/${folderPath}`,
                status: 'Connected',
                image_count: response.s3_config.image_count,
                s3_config: response.s3_config
            };
            
            setSources(prev => [...prev, newSource]);
            if (onSourceAdded) onSourceAdded(newSource);
            handleClose();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleGDriveConnect = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const response = await dataSourceAPI.connectGDrive(gdriveLink);
            const newSource = {
                id: response.data_source_id,
                type: 'gdrive',
                path: `Google Drive > ${gdriveLink.substring(gdriveLink.lastIndexOf('/') + 1)}`,
                status: 'Connected'
            };
            setSources(prev => [...prev, newSource]);
            if (onSourceAdded) onSourceAdded(newSource);
            handleClose();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleBulkUpload = async () => {
        if (!imageSetId) {
            setError('Please save the image set first before uploading a folder');
            return;
        }

        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.zip';
        
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (!file.name.toLowerCase().endsWith('.zip')) {
                setError('Please select a ZIP file containing your image folder');
                return;
            }

            setLoading(true);
            setError('');

            try {
                const response = await imageSetAPI.uploadFolder(imageSetId, file);
                const newSource = {
                    id: 'bulk_' + Date.now(),
                    type: 'bulk_upload',
                    path: `${response.image_count} images from ${file.name}`,
                    status: 'Connected',
                    image_count: response.image_count
                };
                setSources(prev => [...prev, newSource]);
                if (onSourceAdded) onSourceAdded(newSource);
                handleClose();
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        input.click();
    };

    const handleClose = () => {
        setModalView('select');
        setBucketName('');
        setFolderPath('');
        setAccessKey('');
        setSecretKey('');
        setRegion('');
        setGdriveLink('');
        setError('');
        setIsDetectingRegion(false);
        onClose();
    };

    if (!show) return null;

    const renderS3Form = () => (
        <form onSubmit={handleS3Connect}>
            <h3 className="text-xl font-bold mb-4 flex items-center"><Icon type="s3" /> Connect to Amazon S3</h3>
            
            {error && (
                <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
                    <AlertCircle size={16} className="mr-2" />
                    {error}
                </div>
            )}

            <div className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Bucket Name</label>
                    <div className="relative">
                        <Cloud size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                        <input 
                            type="text" 
                            value={bucketName} 
                            onChange={e => setBucketName(e.target.value)} 
                            placeholder="e.g., my-company-images" 
                            required 
                            className="w-full p-2 pl-9 border border-gray-300 rounded-lg" 
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Folder Path (optional)</label>
                    <div className="relative">
                        <Folder size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                        <input 
                            type="text" 
                            value={folderPath} 
                            onChange={e => setFolderPath(e.target.value)} 
                            placeholder="e.g., /products/2025/" 
                            className="w-full p-2 pl-9 border border-gray-300 rounded-lg" 
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Access Key</label>
                    <div className="relative">
                        <Key size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                        <input 
                            type="password" 
                            value={accessKey} 
                            onChange={e => setAccessKey(e.target.value)} 
                            placeholder="••••••••••••••••" 
                            required 
                            className="w-full p-2 pl-9 border border-gray-300 rounded-lg" 
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Secret Key</label>
                     <div className="relative">
                        <Key size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                        <input 
                            type="password" 
                            value={secretKey} 
                            onChange={e => setSecretKey(e.target.value)} 
                            placeholder="••••••••••••••••••••••••" 
                            required 
                            className="w-full p-2 pl-9 border border-gray-300 rounded-lg" 
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                        AWS Region {region && <span className="text-green-600 text-xs">(Selected: {region})</span>}
                    </label>
                    <div className="flex gap-2">
                        <div className="relative flex-1">
                            <Globe size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                            <select 
                                value={region} 
                                onChange={e => setRegion(e.target.value)} 
                                required
                                className="w-full p-2 pl-9 border border-gray-300 rounded-lg"
                                disabled={isDetectingRegion}
                            >
                                <option value="">Select AWS region</option>
                                <option value="us-east-1">US East (N. Virginia)</option>
                                <option value="us-east-2">US East (Ohio)</option>
                                <option value="us-west-1">US West (N. California)</option>
                                <option value="us-west-2">US West (Oregon)</option>
                                <option value="eu-west-1">Europe (Ireland)</option>
                                <option value="eu-west-2">Europe (London)</option>
                                <option value="eu-central-1">Europe (Frankfurt)</option>
                                <option value="ap-south-1">Asia Pacific (Mumbai)</option>
                                <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                                <option value="ap-southeast-2">Asia Pacific (Sydney)</option>
                                <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
                                <option value="ca-central-1">Canada (Central)</option>
                            </select>
                        </div>
                        <button 
                            type="button"
                            onClick={handleDetectRegion}
                            disabled={!bucketName || !accessKey || !secretKey || isDetectingRegion || loading}
                            className="px-4 py-2 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-sm font-medium disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed whitespace-nowrap"
                        >
                            {isDetectingRegion ? 'Detecting...' : 'Auto-detect'}
                        </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                        {region ? 
                            `Region selected: ${region}` : 
                            'Select a region manually or enter credentials and click Auto-detect'
                        }
                    </p>
                </div>
            </div>
            <div className="mt-6 flex justify-between">
                <button 
                    type="button" 
                    onClick={() => setModalView('select')} 
                    className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded-lg"
                >
                    Back
                </button>
                <button 
                    type="submit" 
                    disabled={loading || !region} 
                    className="text-sm bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50"
                >
                    {loading ? 'Connecting...' : 'Connect'}
                </button>
            </div>
        </form>
    );


    const renderBulkUploadForm = () => (
        <div>
            <h3 className="text-xl font-bold mb-4 flex items-center">
                <Folder className="inline-block mr-2" size={20} />
                Bulk Upload (ZIP Folder)
            </h3>
            <p className="text-sm text-gray-600 mb-4">
                Upload a ZIP file containing your image folder. Cost: $0.001 USD per image detected.
            </p>
            
            {error && (
                <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
                    <AlertCircle size={16} className="mr-2" />
                    {error}
                </div>
            )}

            <div 
                className="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center cursor-pointer hover:border-blue-500 hover:bg-gray-50 transition" 
                onClick={handleBulkUpload}
            >
                <UploadCloud size={48} className="mx-auto text-gray-400 mb-4" />
                <p className="font-semibold text-gray-700">Click to select ZIP folder</p>
                <p className="text-sm text-gray-500">Select a ZIP file containing your image folder</p>
                <p className="text-xs text-gray-400 mt-2">Supported: .zip files with .jpg, .png, .bmp, .tiff, .webp images</p>
            </div>
            <div className="mt-6 flex justify-between">
                <button 
                    type="button" 
                    onClick={() => setModalView('select')} 
                    className="text-sm bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded-lg"
                >
                    Back
                </button>
                <button 
                    onClick={handleBulkUpload} 
                    disabled={loading || !imageSetId} 
                    className="text-sm bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50"
                >
                    {loading ? 'Uploading...' : 'Upload ZIP Folder'}
                </button>
            </div>
        </div>
    );

    const renderSelectView = () => (
        <div>
            <h3 className="text-xl font-bold mb-6">Add Data Source</h3>
            <div className="space-y-4">
                <button 
                    onClick={() => setModalView('s3')} 
                    className="w-full flex items-center p-4 border rounded-lg hover:bg-gray-50 transition"
                >
                    <Cloud className="inline-block mr-2" size={20} />
                    Connect to Amazon S3
                </button>
                
                <button 
                    onClick={() => setModalView('bulk_upload')} 
                    className="w-full flex items-center p-4 border rounded-lg hover:bg-gray-50 transition"
                >
                    <Folder className="inline-block mr-2" size={20} />
                    Bulk Upload (ZIP Folder)
                </button>
            </div>
        </div>
    );

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-lg relative">
                <button 
                    onClick={handleClose} 
                    className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
                >
                    <X size={24} />
                </button>
                {modalView === 'select' && renderSelectView()}
                {modalView === 's3' && renderS3Form()}
                {modalView === 'gdrive' && renderGDriveForm()}
                {modalView === 'bulk_upload' && renderBulkUploadForm()}
            </div>
        </div>
    );
};

// Search History Modal Component - Add after AddSourceModal component
const SearchHistoryModal = ({ show, onClose, setView, setResultsData }) => {
    const [searchHistory, setSearchHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [loadingResults, setLoadingResults] = useState(false);

    useEffect(() => {
        if (show) {
            loadSearchHistory();
        }
    }, [show]);

    const loadSearchHistory = async () => {
        try {
            setLoading(true);
            const response = await searchHistoryAPI.getHistory();
            setSearchHistory(response.history);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteItem = async (searchId) => {
        if (!window.confirm('Delete this search from history?')) return;

        try {
            await searchHistoryAPI.deleteHistoryItem(searchId);
            setSearchHistory(prev => prev.filter(item => item.id !== searchId));
        } catch (err) {
            setError(err.message);
        }
    };

    const handleClearAll = async () => {
        if (!window.confirm('Clear all search history? This cannot be undone.')) return;

        try {
            await searchHistoryAPI.clearHistory();
            setSearchHistory([]);
        } catch (err) {
            setError(err.message);
        }
    };

    const handleViewResults = async (item) => {
        try {
            setLoadingResults(true);
            setError('');
            
            console.log('Loading results for search:', item.id);
            
            const response = await searchHistoryAPI.getSearchResults(item.id);
            
            if (response.success && response.results && response.results.length > 0) {
                // Use the stored query image URL from the response
                const queryImageUrl = response.query_image_url || 
                    `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'%3E%3Crect width='200' height='200' fill='%23f3f4f6'/%3E%3Ctext x='100' y='100' text-anchor='middle' dy='0.35em' font-family='Arial' font-size='12' fill='%236b7280'%3E${encodeURIComponent(item.query_image_name || 'Historical Query')}%3C/text%3E%3C/svg%3E`;
                
                const resultsData = {
                    queryImage: queryImageUrl,  // Use the actual stored query image
                    results: response.results,
                    searchCost: 0, // Historical search, no additional cost
                    awsResults: response.results.filter(r => r.search_type === 'aws_rekognition').length,
                    faissResults: response.results.filter(r => r.search_type === 'faiss').length,
                    remainingCredits: 0, // Not applicable for historical results
                    isHistorical: true,
                    searchInfo: {
                        ...response.search_history,
                        originalThreshold: response.search_history.similarity_threshold
                    }
                };

                console.log('Setting results data:', resultsData);
                setResultsData(resultsData);
                onClose();
                setView('results');
                
                // Show informational messages
                if (response.expired_urls > 0) {
                    setTimeout(() => {
                        alert(`Note: ${response.expired_urls} AWS image(s) have expired and show as placeholders. Original search results were valid for 7 days.`);
                    }, 500);
                }
            } else {
                setError('No results found for this search or results have expired');
            }
        } catch (err) {
            console.error('Error loading search results:', err);
            setError(`Failed to load search results: ${err.message}`);
        } finally {
            setLoadingResults(false);
        }
    };

    const getSearchTypeBadge = (searchType) => {
        switch (searchType) {
            case 'aws_rekognition':
                return <span className="px-2 py-1 text-xs font-medium rounded-full bg-orange-100 text-orange-800">AWS</span>;
            case 'faiss':
                return <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">FAISS</span>;
            case 'mixed':
                return <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">Mixed</span>;
            default:
                return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">Unknown</span>;
        }
    };

    const formatDate = (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    };

    if (!show) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] relative flex flex-col">
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <h3 className="text-xl font-bold text-gray-800 flex items-center">
                        <Clock size={24} className="mr-2" />
                        Search History
                    </h3>
                    <div className="flex items-center gap-2">
                        {searchHistory.length > 0 && (
                            <button 
                                onClick={handleClearAll}
                                className="text-sm bg-red-100 hover:bg-red-200 text-red-800 font-semibold py-1 px-3 rounded-lg transition-colors"
                            >
                                Clear All
                            </button>
                        )}
                        <button 
                            onClick={onClose} 
                            className="text-gray-400 hover:text-gray-600"
                        >
                            <X size={24} />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="flex justify-center items-center py-8">
                            <Settings size={24} className="animate-spin text-blue-600 mr-3" />
                            <span>Loading search history...</span>
                        </div>
                    ) : error ? (
                        <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
                            <AlertCircle size={16} className="mr-2" />
                            {error}
                        </div>
                    ) : searchHistory.length === 0 ? (
                        <div className="text-center py-8">
                            <Search size={48} className="mx-auto text-gray-300 mb-4" />
                            <p className="text-gray-500">No search history found.</p>
                            <p className="text-sm text-gray-400">Your searches will appear here for easy reference.</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {searchHistory.map((item) => (
                                <div key={item.id} className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
                                    <div className="flex justify-between items-start">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-2">
                                                <h4 className="font-semibold text-gray-800">
                                                    {item.query_image_name || 'Unknown Image'}
                                                </h4>
                                                {getSearchTypeBadge(item.search_type)}
                                            </div>
                                            
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600 mb-3">
                                                <div>
                                                    <span className="font-medium">Results:</span> {item.results_count}
                                                </div>
                                                <div>
                                                    <span className="font-medium">Time:</span> {item.search_time ? `${item.search_time.toFixed(2)}s` : 'N/A'}
                                                </div>
                                                <div>
                                                    <span className="font-medium">Date:</span> {formatDate(item.created_at)}
                                                </div>
                                            </div>

                                            {item.image_sets && item.image_sets.length > 0 && (
                                                <div className="mb-3">
                                                    <p className="text-sm font-medium text-gray-700 mb-1">Searched in:</p>
                                                    <div className="flex flex-wrap gap-2">
                                                        {item.image_sets.map((set) => (
                                                            <span 
                                                                key={set.id}
                                                                className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded-full"
                                                            >
                                                                {set.name}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {item.results_count > 0 && (
                                              <div className="flex items-center gap-2">
                                                  <button
                                                      onClick={() => handleViewResults(item)}
                                                      disabled={loadingResults}
                                                      className="text-sm bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold py-1 px-3 rounded-lg transition-colors flex items-center disabled:opacity-50"
                                                  >
                                                      {loadingResults ? (
                                                          <>
                                                              <Settings size={14} className="mr-1 animate-spin" />
                                                              Loading...
                                                          </>
                                                      ) : (
                                                          <>
                                                              <Eye size={14} className="mr-1" />
                                                              View Results ({item.results_count})
                                                          </>
                                                      )}
                                                  </button>
                                                  
                                              </div>
                                            )}
                                        </div>
                                        
                                        <button
                                            onClick={() => handleDeleteItem(item.id)}
                                            className="ml-4 text-gray-400 hover:text-red-500 transition-colors"
                                            title="Delete search"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};


const ConfigureSetScreen = ({ selectedSet, setSelectedSet, setView, imageSets, setImageSets, credits, setCredits, dataSources }) => {
  const [setName, setSetName] = useState(selectedSet.name || '');
  const [setDescription, setSetDescription] = useState(selectedSet.description || '');
  const [sources, setSources] = useState(selectedSet.sources || []);
  const [showModal, setShowModal] = useState(false);
  const [calculationState, setCalculationState] = useState('idle');
  const [calculationResult, setCalculationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [bulkUploadInfo, setBulkUploadInfo] = useState(null);
  const [bulkCalculationState, setBulkCalculationState] = useState('idle');
  const [bulkCalculationResult, setBulkCalculationResult] = useState(null);
  const [s3Config, setS3Config] = useState(null); 

  const handleS3Calculate = async () => {
      if (!s3Config) {
          setError('Please connect to S3 first');
          return;
      }

      if (!selectedSet.id) {
          setError('Please save the image set first');
          return;
      }

      setCalculationState('calculating');
      setError('');

      try {
          console.log('Calculating S3 cost with config:', s3Config);
          const result = await s3API.calculateCost(s3Config);
          console.log('S3 cost calculation result:', result);
          
          setCalculationResult({
              imageCount: result.image_count,
              cost: result.cost,
              costUSD: result.cost_usd,
              time: result.estimated_time_minutes
          });
          setCalculationState('calculated');
      } catch (err) {
          console.error('S3 cost calculation error:', err);
          setError(`Cost calculation failed: ${err.message}`);
          setCalculationState('idle');
      }
  };

  // Updated S3 indexing function
  const handleS3StartIndexing = async () => {
      if (!s3Config) {
          setError('Please connect to S3 first');
          return;
      }

      if (credits < calculationResult.cost) {
          setError("Insufficient credits!");
          return;
      }

      setLoading(true);
      setError('');

      try {
          setCredits(c => c - calculationResult.cost);
          
          await s3API.startIndexing(s3Config, selectedSet.id);
          
          const updatedSet = { 
              ...selectedSet, 
              name: setName, 
              description: setDescription, 
              status: 'indexing', 
              progress: 0, 
              image_count: 0,
              source_type: 's3_aws_rekognition'
          };
          
          let setsToUpdate = imageSets.find(s => s.id === selectedSet.id)
              ? imageSets.map(s => s.id === selectedSet.id ? updatedSet : s)
              : [...imageSets, updatedSet];
          
          setImageSets(setsToUpdate);
          setView('dashboard');

          // Poll progress
          const pollProgress = async () => {
              try {
                  const progress = await imageSetAPI.getProgress(selectedSet.id);
                  setImageSets(prevSets => 
                      prevSets.map(s => s.id === selectedSet.id ? { 
                          ...s, 
                          status: progress.status,
                          progress: progress.progress,
                          image_count: progress.indexed_images_count
                      } : s)
                  );
                  
                  if (progress.status === 'indexing' && progress.progress < 100) {
                      setTimeout(pollProgress, 2000);
                  }
              } catch (err) {
                  console.error('Error polling progress:', err);
              }
          };
          
          setTimeout(pollProgress, 2000);
      } catch (err) {
          setError(err.message);
      } finally {
          setLoading(false);
      }
  };

  const handleSave = async () => {
    if (!setName.trim()) {
      setError('Please enter a name for the image set');
      return;
    }

    setLoading(true);
    setError('');

    try {
      if (!selectedSet.id || !imageSets.find(s => s.id === selectedSet.id)) {
        // Create new image set
        const newSet = await imageSetAPI.createImageSet(setName, setDescription);
        const updatedSet = { 
          ...newSet, 
          sources, 
          status: 'draft', 
          progress: 0, 
          image_count: 0 
        };
        setImageSets([...imageSets, updatedSet]);
        setSelectedSet(updatedSet);
      } else {
        // Update existing image set
        const updatedSets = imageSets.map(s =>
          s.id === selectedSet.id ? { ...s, name: setName, description: setDescription, sources } : s
        );
        setImageSets(updatedSets);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleCalculate = async () => {
    if (sources.length === 0) {
      setError('Please add at least one data source before calculating');
      return;
    }

    setCalculationState('calculating');
    setError('');

    try {
      // Get data source IDs from sources
      const dataSourceIds = sources.map(source => source.id).filter(Boolean);
      
      let result;
      if (selectedSet.id && dataSourceIds.length > 0) {
        result = await imageSetAPI.calculateCost(selectedSet.id, dataSourceIds);
      } else {
        // Fallback calculation for new sets
        throw new Error('Please save the image set first');
      }
      
      setCalculationResult({
        imageCount: result.image_count,
        cost: result.cost,
        time: result.estimated_time_minutes
      });
      setCalculationState('calculated');
    } catch (err) {
      setError(err.message);
      // Fallback to mock calculation
      setTimeout(() => {
        const imageCount = Math.floor(Math.random() * (200000 - 5000 + 1) + 5000);
        const cost = Math.ceil(imageCount * 0.1);
        const time = Math.ceil(imageCount / 1000) * 5;
        setCalculationResult({ imageCount, cost, time });
        setCalculationState('calculated');
      }, 2000);
    }
  };

  const handleStartIndexing = async () => {
    if (credits < calculationResult.cost) {
        setError("Insufficient credits!");
        return;
    }

    setLoading(true);
    setError('');

    try {
      setCredits(c => c - calculationResult.cost);
      
      // Get data source IDs from sources
      const dataSourceIds = sources.map(source => source.id).filter(Boolean);
      await imageSetAPI.startIndexing(selectedSet.id, dataSourceIds);
      
      const updatedSet = { 
        ...selectedSet, 
        name: setName, 
        description: setDescription, 
        sources, 
        status: 'indexing', 
        progress: 0, 
        image_count: 0 
      };
      
      let setsToUpdate = imageSets.find(s => s.id === selectedSet.id)
        ? imageSets.map(s => s.id === selectedSet.id ? updatedSet : s)
        : [...imageSets, updatedSet];
      
      setImageSets(setsToUpdate);
      setView('dashboard');

      // Enhanced progress polling for AWS Rekognition
      const pollProgress = async () => {
        try {
          const progress = await imageSetAPI.getProgress(selectedSet.id);
          setImageSets(prevSets => 
            prevSets.map(s => s.id === selectedSet.id ? { 
              ...s, 
              status: progress.status,
              progress: progress.progress,
              image_count: progress.indexed_images_count
            } : s)
          );
          
          if (progress.status === 'indexing' && progress.progress < 100) {
            setTimeout(pollProgress, 2000); // Poll every 2 seconds during indexing
          }
        } catch (err) {
          console.error('Error polling progress:', err);
        }
      };
      
      setTimeout(pollProgress, 2000); // Start polling after 2 seconds
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Bulk upload functions
  const handleBulkCalculate = async () => {
    if (!bulkUploadInfo) {
      setError('Please upload a folder first before calculating');
      return;
    }

    setBulkCalculationState('calculating');
    setError('');

    try {
      const result = await imageSetAPI.calculateCostBulk(selectedSet.id);
      
      setBulkCalculationResult({
        imageCount: result.image_count,
        cost: result.cost,
        time: result.estimated_time_minutes
      });
      setBulkCalculationState('calculated');
    } catch (err) {
      setError(err.message);
      setBulkCalculationState('idle');
    }
  };

  const handleBulkStartIndexing = async () => {
    if (credits < bulkCalculationResult.cost) {
      setError("Insufficient credits!");
      return;
    }

    setLoading(true);
    setError('');

    try {
      setCredits(c => c - bulkCalculationResult.cost);
      
      await imageSetAPI.startIndexingBulk(selectedSet.id);
      
      const updatedSet = { 
        ...selectedSet, 
        name: setName, 
        description: setDescription, 
        status: 'indexing', 
        progress: 0, 
        image_count: 0,
        sources: [...sources]
      };
      
      let setsToUpdate = imageSets.find(s => s.id === selectedSet.id)
        ? imageSets.map(s => s.id === selectedSet.id ? updatedSet : s)
        : [...imageSets, updatedSet];
      
      setImageSets(setsToUpdate);
      setView('dashboard');

      // Enhanced progress polling for FAISS indexing
      const pollProgress = async () => {
        try {
          const progress = await imageSetAPI.getProgress(selectedSet.id);
          console.log('Progress update:', progress); // Debug log
          
          setImageSets(prevSets => 
            prevSets.map(s => s.id === selectedSet.id ? { 
              ...s, 
              status: progress.status,
              progress: progress.progress,
              image_count: progress.indexed_images_count
            } : s)
          );
          
          // Continue polling if still indexing
          if (progress.status === 'indexing' && progress.progress < 100) {
            setTimeout(pollProgress, 1000); // Poll every 1 second for more responsive updates
          } else if (progress.status === 'ready') {
            // Indexing completed successfully
            console.log('Indexing completed successfully');
          } else if (progress.status === 'error') {
            // Indexing failed
            console.log('Indexing failed');
          }
        } catch (err) {
          console.error('Error polling progress:', err);
          // Continue polling even on error, but less frequently
          setTimeout(pollProgress, 3000);
  }
};

// Start polling immediately after starting indexing
setTimeout(pollProgress, 500); // Start polling after 2 seconds
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSourceAdded = (newSource) => {
      if (newSource.type === 's3') {
          // Store S3 configuration for direct AWS operations
          setS3Config(newSource.s3_config);
          setCalculationState('idle');
          setCalculationResult(null);
      } else if (newSource.type === 'bulk_upload') {
          setBulkUploadInfo({
              filename: newSource.path,
              imageCount: newSource.image_count
          });
          setBulkCalculationState('idle');
          setBulkCalculationResult(null);
      }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <AddSourceModal 
        show={showModal} 
        onClose={() => setShowModal(false)} 
        setSources={setSources}
        onSourceAdded={handleSourceAdded}
        imageSetId={selectedSet.id}
      />
      
      <button 
        onClick={() => setView('dashboard')} 
        className="mb-6 inline-flex items-center text-blue-600 hover:text-blue-800"
      >
        <ArrowLeft size={16} className="mr-2" /> Back to Dashboard
      </button>
      
      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">
          {selectedSet.name ? 'Configure Image Set' : 'Create New Image Set'}
        </h2>
        
        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
            <AlertCircle size={16} className="mr-2" />
            {error}
          </div>
        )}

        <div className="space-y-6">
          <div>
            <label htmlFor="setName" className="block text-sm font-medium text-gray-700 mb-1">Set Name</label>
            <input 
              type="text" 
              id="setName" 
              value={setName} 
              onChange={e => setSetName(e.target.value)} 
              className="w-full p-2 border border-gray-300 rounded-lg" 
              placeholder="Enter image set name"
            />
          </div>
          <div>
            <label htmlFor="setDescription" className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea 
              id="setDescription" 
              value={setDescription} 
              onChange={e => setSetDescription(e.target.value)} 
              rows="3" 
              className="w-full p-2 border border-gray-300 rounded-lg"
              placeholder="Enter description for this image set"
            ></textarea>
          </div>
        </div>

        <div className="mt-8 text-right">
          <button 
            onClick={handleSave} 
            disabled={loading || !setName.trim()}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        <hr className="my-8" />

        <div>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-bold text-gray-800">Data Sources</h3>
            <button 
              onClick={() => setShowModal(true)} 
              className="bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold py-2 px-4 rounded-lg inline-flex items-center transition-colors text-sm"
            >
              <Plus size={16} className="mr-2" /> Add Data Source
            </button>
          </div>
          <div className="space-y-3">
            {sources.length > 0 ? sources.map((source, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
                <div className="flex items-center">
                  <Icon type={source.type} />
                  <span className="text-sm text-gray-700">{source.path}</span>
                </div>
                <div className="flex items-center space-x-2">
                    <span className="text-sm text-green-600 font-medium">{source.status}</span>
                    <button 
                      onClick={() => {
                        setSources(sources.filter((_, i) => i !== index));
                        setCalculationState('idle');
                        setCalculationResult(null);
                        // Reset bulk upload state if removing bulk upload source
                        if (source.type === 'bulk_upload') {
                          setBulkUploadInfo(null);
                          setBulkCalculationState('idle');
                          setBulkCalculationResult(null);
                        }
                      }} 
                      className="text-gray-400 hover:text-red-500"
                    >
                        <Trash2 size={16} />
                    </button>
                </div>
              </div>
            )) : (
              <p className="text-sm text-gray-500 text-center py-4">
                No data sources connected. Add one to begin.
              </p>
            )}
          </div>
        </div>


        {/* Bulk Upload Indexing Section */}
        {sources.some(source => source.type === 'bulk_upload') && (
          <>
            <hr className="my-8" />
            <div>
              <h3 className="text-xl font-bold text-gray-800 mb-4">Bulk Upload Indexing (FAISS)</h3>
              {bulkCalculationState === 'idle' && (
                <div className="text-center p-6 bg-gray-50 rounded-lg border border-dashed">
                  <p className="text-gray-600 mb-4">
                    Calculate the cost for indexing your uploaded images using FAISS face recognition.
                  </p>
                  <p className="text-sm text-gray-500 mb-4">
                    Cost: $0.001 USD per image detected
                  </p>
                  <button 
                    onClick={handleBulkCalculate} 
                    disabled={!bulkUploadInfo || loading} 
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    Calculate Image Count & Cost
                  </button>
                  {!bulkUploadInfo && (
                    <p className="text-sm text-gray-500 mt-2">Please upload a folder first</p>
                  )}
                </div>
              )}
              {bulkCalculationState === 'calculating' && (
                <div className="text-center p-6 bg-gray-50 rounded-lg">
                  <div className="flex justify-center items-center">
                    <Settings size={24} className="animate-spin text-blue-600 mr-3" />
                    <p className="text-gray-600">Calculating... Analyzing uploaded images, please wait.</p>
                  </div>
                </div>
              )}
              {bulkCalculationState === 'calculated' && bulkCalculationResult && (
                <div className="p-6 bg-blue-50 border-l-4 border-blue-500 rounded-r-lg">
                  <h4 className="font-bold text-lg text-gray-800 mb-4">Calculation Complete</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-center">
                    <div>
                      <p className="text-sm text-gray-500">Images Found</p>
                      <p className="text-2xl font-bold text-blue-600">
                        {bulkCalculationResult.imageCount.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Estimated Indexing Time</p>
                      <p className="text-2xl font-bold text-blue-600">~{bulkCalculationResult.time} mins</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Indexing Cost</p>
                      <p className="text-2xl font-bold text-blue-600">
                        ${bulkCalculationResult.cost.toFixed(3)} USD
                      </p>
                    </div>
                  </div>
                  <div className="text-center">
                    {credits < bulkCalculationResult.cost ? (
                      <div className="p-4 bg-red-100 text-red-800 rounded-lg">
                        <p className="font-bold">Insufficient Credits</p>
                        <p>You need ${(bulkCalculationResult.cost - credits).toFixed(3)} more credits to start.</p>
                        <button 
                          onClick={() => setCredits(c => c + 10)} 
                          className="mt-2 bg-red-500 hover:bg-red-600 text-white font-semibold py-1 px-3 rounded-lg"
                        >
                          Add Credits
                        </button>
                      </div>
                    ) : (
                      <button 
                        onClick={handleBulkStartIndexing} 
                        disabled={loading}
                        className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {loading ? 'Starting...' : `Index Now ($${bulkCalculationResult.cost.toFixed(3)} USD)`}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {/* S3 AWS Rekognition Indexing Section */}
        {s3Config && (
            <>
                <hr className="my-8" />
                <div>
                    <h3 className="text-xl font-bold text-gray-800 mb-4">AWS Indexing (S3)</h3>
                    {calculationState === 'idle' && (
                        <div className="text-center p-6 bg-gray-50 rounded-lg border border-dashed">
                            <p className="text-gray-600 mb-4">
                                Calculate cost for indexing {s3Config.image_count} images from S3 using AWS .
                            </p>
                            <button 
                                onClick={handleS3Calculate} 
                                disabled={!setName.trim() || loading} 
                                className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                            >
                                Calculate AWS Cost
                            </button>
                            {!setName.trim() && (
                                <p className="text-sm text-gray-500 mt-2">Please enter a name and save first</p>
                            )}
                        </div>
                    )}
                    {calculationState === 'calculating' && (
                        <div className="text-center p-6 bg-gray-50 rounded-lg">
                            <div className="flex justify-center items-center">
                                <Settings size={24} className="animate-spin text-blue-600 mr-3" />
                                <p className="text-gray-600">Calculating AWS costs...</p>
                            </div>
                        </div>
                    )}
                    {calculationState === 'calculated' && calculationResult && (
                        <div className="p-6 bg-blue-50 border-l-4 border-blue-500 rounded-r-lg">
                            <h4 className="font-bold text-lg text-gray-800 mb-4">AWS Cost Calculation</h4>
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 text-center">
                                <div>
                                    <p className="text-sm text-gray-500">Images Found (S3)</p>
                                    <p className="text-2xl font-bold text-blue-600">
                                        {calculationResult.imageCount.toLocaleString()}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Estimated Time</p>
                                    <p className="text-2xl font-bold text-blue-600">~{calculationResult.time} mins</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Cost (USD)</p>
                                    <p className="text-2xl font-bold text-green-600">
                                        ${(calculationResult.costUSD || (calculationResult.cost / 1000)).toFixed(3)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Cost (Credits)</p>
                                    <p className="text-2xl font-bold text-blue-600">
                                        {calculationResult.cost.toLocaleString()} Credits
                                    </p>
                                </div>
                            </div>
                            <div className="text-center">
                                {credits < calculationResult.cost ? (
                                    <div className="p-4 bg-red-100 text-red-800 rounded-lg">
                                        <p className="font-bold">Insufficient Credits</p>
                                        <p>You need {(calculationResult.cost - credits).toLocaleString()} more credits to start.</p>
                                        <button 
                                            onClick={() => setCredits(c => c + 10000)} 
                                            className="mt-2 bg-red-500 hover:bg-red-600 text-white font-semibold py-1 px-3 rounded-lg"
                                        >
                                            Add Credits
                                        </button>
                                    </div>
                                ) : (
                                    <button 
                                        onClick={handleS3StartIndexing} 
                                        disabled={loading}
                                        className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-lg transition-colors disabled:opacity-50"
                                    >
                                        {loading ? 'Starting AWS Rekognition...' : `Start AWS Rekognition Indexing (${calculationResult.cost.toLocaleString()} Credits)`}
                                    </button>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </>
        )}
      </div>
    </div>
  );
};



const SearchScreen = ({ setView, imageSets, setResults }) => {
    const [uploadedImage, setUploadedImage] = useState(null);
    const [uploadedFile, setUploadedFile] = useState(null);
    const [selectedSets, setSelectedSets] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [error, setError] = useState('');

    const handleImageUpload = (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setUploadedFile(file);
            setUploadedImage(URL.createObjectURL(file));
            setError('');
        }
    };

    const toggleSetSelection = (setId) => {
        setSelectedSets(prev => 
            prev.includes(setId) ? prev.filter(id => id !== setId) : [...prev, setId]
        );
    };

    const handleSearch = async () => {
        if (!uploadedFile || selectedSets.length === 0) {
            setError('Please upload an image and select at least one image set');
            return;
        }

        // Calculate search cost preview
        const awsSetCount = selectedSets.filter(setId => {
            const set = imageSets.find(s => s.id === setId);
            return set && set.source_type === 's3_aws';
        }).length;
        
        const bulkSetCount = selectedSets.filter(setId => {
            const set = imageSets.find(s => s.id === setId);
            return set && set.source_type === 'bulk_upload';
        }).length;

        const estimatedCost = (awsSetCount * 1.0) + (bulkSetCount * 0.1);
        
        // Show cost confirmation if significant
        if (estimatedCost > 0.5) {
            const confirmed = window.confirm(
                `This search will cost approximately ${estimatedCost.toFixed(1)} credits:\n` +
                `• AWS Rekognition searches: ${awsSetCount} × 1.0 = ${awsSetCount.toFixed(1)} credits\n` +
                `• FAISS searches: ${bulkSetCount} × 0.1 = ${(bulkSetCount * 0.1).toFixed(1)} credits\n\n` +
                `Continue with search?`
            );
            
            if (!confirmed) return;
        }

        setIsSearching(true);
        setError('');

        try {
            const result = await searchAPI.searchImages(uploadedFile, selectedSets);
            
            // Show cost breakdown in results
            if (result.search_cost && result.search_cost > 0) {
                console.log(`Search completed. Cost: ${result.search_cost} credits. Remaining: ${result.remaining_credits} credits`);
            }
            
            setResults({
                queryImage: uploadedImage,
                results: result.results,
                searchCost: result.search_cost,
                awsResults: result.aws_results || 0,
                faissResults: result.faiss_results || 0,
                remainingCredits: result.remaining_credits
            });
            setView('results');
        } catch (err) {
            setError(err.message);
        } finally {
            setIsSearching(false);
        }
    };

    const readySets = imageSets.filter(s => s.status === 'ready');

    return (
        <div className="p-4 sm:p-6 lg:p-8 flex justify-center items-center min-h-[calc(100vh-80px)]">
            <div className="w-full max-w-2xl text-center">
                <div className="bg-white p-8 rounded-lg shadow-lg border border-gray-200">
                    <h2 className="text-3xl font-bold text-gray-800 mb-2">Reverse Image Search</h2>
                    <p className="text-gray-600 mb-8">Upload an image to find similar ones in your indexed sets.</p>
                    
                    {error && (
                        <div className="mb-6 p-3 bg-red-100 border border-red-400 text-red-700 rounded flex items-center">
                            <AlertCircle size={16} className="mr-2" />
                            {error}
                        </div>
                    )}
                    
                    <div className="mb-6">
                        <label htmlFor="image-upload" className="cursor-pointer">
                            <div className="border-2 border-dashed border-gray-300 rounded-lg p-10 hover:border-blue-500 hover:bg-gray-50 transition-colors">
                                {uploadedImage ? (
                                    <img 
                                      src={uploadedImage} 
                                      alt="Uploaded preview" 
                                      className="max-h-48 mx-auto rounded-lg" 
                                    />
                                ) : (
                                    <div className="flex flex-col items-center text-gray-500">
                                        <UploadCloud size={48} className="mb-4" />
                                        <span className="font-semibold">Drag & drop an image here</span>
                                        <span className="text-sm">or click to browse</span>
                                    </div>
                                )}
                            </div>
                        </label>
                        <input 
                          id="image-upload" 
                          type="file" 
                          className="hidden" 
                          accept="image/*" 
                          onChange={handleImageUpload} 
                        />
                    </div>

                    <div className="mb-8 text-left">
                        <label className="font-semibold text-gray-700 mb-2 block">Search In:</label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {readySets.map(set => (
                            <button 
                              key={set.id} 
                              onClick={() => toggleSetSelection(set.id)} 
                              className={`flex items-center p-3 border rounded-lg text-left transition-colors ${
                                selectedSets.includes(set.id) 
                                  ? 'bg-blue-100 border-blue-500' 
                                  : 'hover:bg-gray-50'
                              }`}
                            >
                              <div className={`w-5 h-5 mr-3 border-2 rounded flex-shrink-0 flex items-center justify-center ${
                                selectedSets.includes(set.id) 
                                  ? 'bg-blue-600 border-blue-600' 
                                  : 'border-gray-300'
                              }`}>
                                {selectedSets.includes(set.id) && <Check size={16} className="text-white" />}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-medium text-sm text-gray-800">{set.name}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <SourceTypeBadge 
                                    sourceType={set.source_type} 
                                    sourceDisplay={set.source_display}
                                    className="text-xs"
                                  />
                                  <span className="text-xs text-gray-500">
                                    {set.image_count?.toLocaleString() || 0} images
                                  </span>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                        {readySets.length === 0 && (
                            <p className="text-gray-500 text-sm">
                              No image sets ready for search. Please create and index an image set first.
                            </p>
                        )}
                    </div>

                    <button 
                        onClick={handleSearch}
                        disabled={!uploadedImage || selectedSets.length === 0 || isSearching}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex justify-center items-center"
                    >
                        {isSearching ? (
                            <>
                                <Settings size={20} className="animate-spin mr-2" />
                                Searching...
                            </>
                        ) : (
                            <>
                                <Search size={20} className="mr-2" />
                                Search
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

const ResultsScreen = ({ setView, resultsData }) => {
    const getPillColor = (similarity) => {
        if (similarity >= 90) return 'bg-green-100 text-green-800';
        if (similarity >= 80) return 'bg-yellow-100 text-yellow-800';
        return 'bg-orange-100 text-orange-800';
    };

    // Sort results by similarity score in descending order and take only top 3
    const sortedResults = [...resultsData.results]
        .sort((a, b) => b.similarity_score - a.similarity_score)
        .slice(0, 3);

    return (
        <div className="p-4 sm:p-6 lg:p-8">
            <button 
                onClick={() => setView('search')} 
                className="mb-6 inline-flex items-center text-blue-600 hover:text-blue-800"
            >
                <ArrowLeft size={16} className="mr-2" /> Start a New Search
            </button>
            <div className="flex flex-col lg:flex-row gap-8">
                <div className="lg:w-1/4">
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 sticky top-8">
                        <h3 className="font-bold text-lg mb-4">Query Image</h3>
                        <img 
                            src={resultsData.queryImage} 
                            alt="Query" 
                            className="rounded-lg w-full" 
                        />
                        <p className="text-sm text-gray-500 mt-4">
                            Showing top 3 results sorted by similarity score.
                        </p>
                        
                        {/* Search Cost and Breakdown */}
                        {resultsData.searchCost && resultsData.searchCost > 0 && (
                            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                                <p className="text-xs font-semibold text-blue-800 mb-2">SEARCH COST</p>
                                <div className="space-y-1 text-xs">
                                    <div className="flex justify-between">
                                        <span>Total Cost:</span>
                                        <span className="font-bold">{resultsData.searchCost.toFixed(1)} credits</span>
                                    </div>
                                    {resultsData.awsResults > 0 && (
                                        <div className="flex justify-between text-orange-600">
                                            <span>AWS Results:</span>
                                            <span>{resultsData.awsResults}</span>
                                        </div>
                                    )}
                                    {resultsData.faissResults > 0 && (
                                        <div className="flex justify-between text-green-600">
                                            <span>FAISS Results:</span>
                                            <span>{resultsData.faissResults}</span>
                                        </div>
                                    )}
                                    {resultsData.remainingCredits && (
                                        <div className="flex justify-between pt-1 border-t border-blue-200">
                                            <span>Remaining:</span>
                                            <span className="font-bold">{resultsData.remainingCredits.toLocaleString()} credits</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
                <div className="lg:w-3/4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                        {sortedResults.map((result, index) => (
                            <div 
                                key={result.image_id} 
                                className="bg-white rounded-lg shadow-sm overflow-hidden border border-gray-200"
                            >
                                <div className="relative">
                                    <img 
                                        src={result.image_path} 
                                        alt={`Match ${result.image_id}`} 
                                        className="w-full h-48 object-cover" 
                                    />
                                    <div className={`absolute top-2 right-2 px-2 py-1 text-xs font-bold rounded-full ${getPillColor(result.similarity_score)}`}>
                                        {Math.round(result.similarity_score)}% Match
                                    </div>
                                    <div className="absolute bottom-2 left-2 px-2 py-1 text-xs font-bold bg-black bg-opacity-70 text-white rounded">
                                        ID: {result.image_id}
                                    </div>
                                    {/* Source type indicator */}
                                    <div className="absolute bottom-2 right-2">
                                        <SourceTypeBadge 
                                            sourceType={result.source_type} 
                                            sourceDisplay=""
                                            className="text-xs bg-black bg-opacity-70 text-white border-none"
                                        />
                                    </div>
                                </div>
                                <div className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <p className="text-xs text-gray-500 font-semibold uppercase">Image ID</p>
                                    </div>
                                    <p className="text-sm font-medium text-gray-800 mb-2">
                                        {result.image_id}
                                    </p>
                                    <div className="flex items-center justify-between mb-2">
                                        <p className="text-xs text-gray-500 font-semibold uppercase">Source</p>
                                        <SourceTypeBadge 
                                            sourceType={result.source_type} 
                                            sourceDisplay=""
                                            className="text-xs"
                                        />
                                    </div>
                                    <p className="text-sm font-medium text-gray-800 truncate">
                                        {result.image_set_name}
                                    </p>
                                    <p className="text-xs text-gray-500 font-semibold uppercase mt-2">Search Method</p>
                                    <p className="text-sm font-medium text-gray-600">
                                        {result.search_type === 'aws_rekognition' ? 'AWS' : 'FAISS (Local)'}
                                    </p>
                                    <p className="text-xs text-gray-500 font-semibold uppercase mt-2">Similarity Score</p>
                                    <p className="text-lg font-bold text-blue-600">
                                        {Math.round(result.similarity_score)}%
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

const MainApplication = ({ onLogout, user }) => {
  const [view, setView] = useState('dashboard');
  const [imageSets, setImageSets] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  const [selectedSet, setSelectedSet] = useState(null);
  const [credits, setCredits] = useState(user?.credits || 1500);
  const [resultsData, setResultsData] = useState({ queryImage: null, results: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSearchHistory, setShowSearchHistory] = useState(false); 

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        // Load image sets
        const sets = await imageSetAPI.getImageSets();
        setImageSets(sets.map(set => ({
          ...set,
          // Normalize status names
          status: set.status === 'ready' ? 'ready' : set.status
        })));

        // Load data sources
        try {
          const sources = await dataSourceAPI.getDataSources();
          setDataSources(sources);
        } catch (err) {
          console.warn('Failed to load data sources:', err);
        }

        // Update credits from user data
        if (user?.credits !== undefined) {
          setCredits(user.credits);
        }

      } catch (err) {
        console.error('Failed to load data:', err);
        setError('Failed to load data. Using demo data.');
        
        // Set some mock data as fallback
        setImageSets([
          {
            id: 1,
            name: 'University Student Photos 2024',
            description: 'All official student ID photos for the current academic year.',
            image_count: 98500,
            status: 'ready',
            progress: 100,
            sources: [
              { type: 's3', path: 's3://university-photos-2024/students/', status: 'Connected' },
            ],
          },
          {
            id: 2,
            name: 'CCTV Archive - Main Campus',
            description: 'Frames from security cameras in Q3.',
            image_count: 0,
            status: 'indexing',
            progress: 35,
            sources: [
              { type: 's3', path: 's3://cctv-main-campus/q3-frames/', status: 'Connected' },
              { type: 'gdrive', path: 'Google Drive > /Security/Extra_Footage', status: 'Connected' },
            ],
          },
        ]);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [user]);

  const handleLogout = () => {
    authAPI.logout();
    onLogout();
  };
  
  const handleDeleteImageSet = (imageSetId) => {
    setImageSets(prevSets => prevSets.filter(set => set.id !== imageSetId));
  };
  const Header = () => (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
      <div className="mx-auto max-w-screen-xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex-1 md:flex md:items-center md:gap-12">
            <button 
                className="flex items-center text-blue-600" 
                onClick={() => setView('dashboard')}
            >
              <Eye size={28} />
              <span className="text-xl font-bold ml-2">Orcan VisionTrace</span>
            </button>
          </div>
          <div className="flex items-center gap-4">
            <nav className="hidden md:block">
              <ul className="flex items-center gap-6 text-sm">
                <li>
                    <button 
                        className={`transition hover:text-gray-500/75 font-medium ${
                            view === 'search' ? 'text-blue-600' : 'text-gray-500'
                        }`} 
                        onClick={() => setView('search')}
                    >
                        Search
                    </button>
                </li>
                <li>
                    <button 
                        className={`transition hover:text-gray-500/75 font-medium ${
                            view === 'dashboard' || view === 'configureSet' ? 'text-blue-600' : 'text-gray-500'
                        }`} 
                        onClick={() => setView('dashboard')}
                    >
                        Image Sets
                    </button>
                </li>
                <li>
                    <button 
                        onClick={() => setShowSearchHistory(true)}
                        className="text-gray-500 transition hover:text-gray-500/75 font-medium flex items-center"
                    >
                        <Clock size={16} className="mr-1" />
                        History
                    </button>
                </li>
                
              </ul>
            </nav>
            <div className="flex items-center gap-4">
                <div className="text-sm text-gray-600">
                    {credits.toLocaleString()} credits
                </div>
                <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                    <span className="font-bold text-gray-600">
                        {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                    </span>
                </div>
                <button 
                    onClick={handleLogout} 
                    title="Logout" 
                    className="text-gray-500 hover:text-red-600 transition-colors"
                >
                    <LogOut size={20} />
                </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );

  const renderView = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center min-h-[calc(100vh-80px)]">
          <div className="flex items-center">
            <Settings size={24} className="animate-spin text-blue-600 mr-3" />
            <span className="text-gray-600">Loading...</span>
          </div>
        </div>
      );
    }

    switch (view) {
      case 'dashboard':
        return (
          <DashboardScreen 
            imageSets={imageSets} 
            setView={setView} 
            setSelectedSet={setSelectedSet} 
            user={user}
            credits={credits} 
            setCredits={setCredits}
            onDeleteImageSet={handleDeleteImageSet}
          />
        );
      case 'configureSet':
        return (
            <ConfigureSetScreen 
                selectedSet={selectedSet} 
                setSelectedSet={setSelectedSet} 
                setView={setView} 
                imageSets={imageSets} 
                setImageSets={setImageSets} 
                credits={credits} 
                setCredits={setCredits}
                dataSources={dataSources}
            />
        );
      case 'search':
        return <SearchScreen setView={setView} imageSets={imageSets} setResults={setResultsData} />;
      case 'results':
        return <ResultsScreen setView={setView} resultsData={resultsData} />;
      default:
        return (
          <DashboardScreen 
            imageSets={imageSets} 
            setView={setView} 
            setSelectedSet={setSelectedSet} 
            user={user}
            credits={credits} 
            setCredits={setCredits}
            onDeleteImageSet={handleDeleteImageSet}
          />
        );
    }
  };

  return (
    <div className="bg-gray-50 min-h-screen font-sans">
      <Header />
      <SearchHistoryModal 
        show={showSearchHistory} 
        onClose={() => setShowSearchHistory(false)}
        setView={setView}
        setResultsData={setResultsData}
      />
      {error && (
        <div className="mx-auto max-w-screen-xl px-4 sm:px-6 lg:px-8 pt-4">
          <div className="p-3 bg-yellow-100 border border-yellow-400 text-yellow-700 rounded flex items-center">
            <AlertCircle size={16} className="mr-2" />
            {error}
          </div>
        </div>
      )}
      <main className="mx-auto max-w-screen-xl">
        {renderView()}
      </main>
    </div>
  );
}

export default function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    // Check if user is already logged in
    useEffect(() => {
        const checkAuth = async () => {
            const token = localStorage.getItem('token');
            if (token) {
                try {
                    const userData = await authAPI.getCurrentUser();
                    setUser(userData);
                    setIsLoggedIn(true);
                } catch (err) {
                    console.error('Failed to get user data:', err);
                    // Token might be expired
                    localStorage.removeItem('token');
                }
            }
            setLoading(false);
        };

        checkAuth();
    }, []);

    const handleLogin = async () => {
        try {
            const userData = await authAPI.getCurrentUser();
            setUser(userData);
            setIsLoggedIn(true);
        } catch (err) {
            console.error('Failed to get user data after login:', err);
            setIsLoggedIn(true); // Still allow login even if user data fetch fails
        }
    };

    const handleLogout = () => {
        setUser(null);
        setIsLoggedIn(false);
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="flex items-center">
                    <Settings size={24} className="animate-spin text-blue-600 mr-3" />
                    <span className="text-gray-600">Loading...</span>
                </div>
            </div>
        );
    }

    if (!isLoggedIn) {
        return <AuthPage onLogin={handleLogin} />;
    }

    return <MainApplication onLogout={handleLogout} user={user} />;
}